"""Three probes that ask a reader to point at text, not to pick a side.

**The measured problem.** The measurement pool, asked *"which of these two do you start"*,
returns our listings over published serials at 15/16, 16/16 with no declared taste, and
**24 of 24 against the operator's own named favourites** — Paranoid Mage, Mark of the Crijik,
The Calamitous Bob. Position is balanced and both conditional rates are 1.0, so there is nothing
for order to explain. A question that returns 1.0 against every pool cannot be fixed by a better
pool: **the question is blind.**

**Why it is blind, and it is not mysterious.** *Which do you start* is a purchase decision, and a
purchase decision runs on premise. The operator reads for something else entirely, and has named
the same classes in every session: terms that mean nothing, sentences that do not connect,
phrases that sound specific and name nothing. None of those changes which book somebody buys off
a shelf; all of them are what makes the prose bad.

**And the one counter that existed asked the wrong question.** The retired definition screen's
`undefined_words` reads *"words used as if you already knew them, where you were never told what
they mean"* — a **definition** counter. It flags `sects`, `slayers`, `class`: genre furniture
every reader of this genre parses on sight, and the operator's own reading of that class of term
is *"extremely clear and clever, I have zero clarity complaints"*.

`house.CLARITY` — written by the operator, and corrected twice by them — states the test the
screen never adopted:

> A term the reader has not met needs a reason to be there before it needs anything else, and
> then **a consequence rather than a definition**: the sentence carrying it says what it does to
> somebody. [...] the test is whether they could say **what it changes for the person it happens
> to**.

`sects` passes that test. `repro steps`, `loot that works` and `a patch of notes` do not. So
probe one is the rule's own test, asked for the first time.

**All three fields are quote fields.** A reader points at a span; nothing rates, ranks, orders or
compares. That is E6 — naming what is there — the one elicitation frame that survived §87-§89,
and it is why these may be asked at all where a verdict may not (§89's 4,676x, §97.4).

### The reading, fixed before the run

Per blurb, the mean count of spans quoted, ours against the summit set.

| | reading |
| --- | --- |
| ours > summits, intervals disjoint | that probe sees what the operator sees, and
  is the first instrument in this project that does |
| intervals overlap | that probe is blind too, and is reported as such rather than
  as a small effect |
| summits > ours | the probe counts something the operator's own favourites do more of. Withdrawn |

**No probe gates anything here.** A count that separates earns the right to be *reported* beside
a listing; gating is a later decision with §61's four attainability checks in front of it.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "src"))

from blurb_readers import READERS  # noqa: E402

from litharness.domain.generation import CompletionRequest  # noqa: E402
from litharness.providers import build_default_registry  # noqa: E402

DERIVED = HERE / "derived"
RESULTS = HERE / "results"

PROBE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["unfollowable", "reread", "empty"],
    "properties": {
        "unfollowable": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Quote any term where you could NOT say what it changes for the person it "
                "happens to. A term you have never met is fine if the sentence carrying it "
                "tells you what it does to somebody — quote only the ones that buy you "
                "nothing. Empty list if none."
            ),
        },
        "reread": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Quote any sentence you had to read twice: because it could be taken two "
                "ways, because you lost track of who or what it was about, or because it did "
                "not follow from the sentence before it. Empty list if none."
            ),
        },
        "empty": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Quote any phrase that sounds like it is telling you something specific and "
                "names nothing you could picture. Empty list if none."
            ),
        },
    },
}

_ASK = (
    "That is the back-cover copy of a book you just picked up, and you read it once at normal "
    "speed. Point at the places it went wrong for you, quoting each one. Quote nothing that "
    "worked."
)

FIELDS = ("unfollowable", "reread", "empty")


def probe(registry: Any, text: str) -> dict[str, Any]:
    """Four readers over one blurb. Returns the per-field counts and every span quoted."""
    spans: dict[str, list[str]] = {name: [] for name in FIELDS}
    answered = 0
    for reader in READERS:
        request = CompletionRequest(
            prompt=f"{text.strip()}\n\n---\n\n{_ASK}",
            system=reader.system(),
            schema=PROBE_SCHEMA,
            max_output_tokens=900,
            profile="reader.perceive.v0",
            call_class="generation",
            timeout_seconds=300.0,
        )
        try:
            result, _ = registry.complete(request)
        except Exception as error:  # an outage is a fact about the day, not about the blurb
            print(f"    {reader.reader_id}: {str(error)[:100]}", file=sys.stderr)
            continue
        if not isinstance(result.parsed, dict):
            continue
        answered += 1
        for name in FIELDS:
            spans[name].extend(
                str(item).strip()
                for item in (result.parsed.get(name) or [])
                if str(item).strip()
            )
    return {"answered": answered, "spans": spans} | {
        name: len(spans[name]) for name in FIELDS
    }


def band(values: list[float]) -> tuple[float, float, float]:
    if not values:
        return (float("nan"),) * 3
    mean = statistics.mean(values)
    if len(values) < 2:
        return (mean, mean, mean)
    half = 1.96 * statistics.stdev(values) / (len(values) ** 0.5)
    return (round(mean - half, 2), round(mean, 2), round(mean + half, 2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summits", default=str(DERIVED / "summit-set.json"))
    parser.add_argument("--ours", nargs="+", required=True)
    parser.add_argument("--each", type=int, default=6)
    parser.add_argument("--out", type=Path, default=RESULTS / "blurb-perception.json")
    args = parser.parse_args(argv)

    summits = json.loads(Path(args.summits).read_text(encoding="utf-8"))[: args.each]
    registry = build_default_registry()

    tiers: dict[str, list[dict[str, Any]]] = {"summits": [], "ours": []}
    for row in summits:
        got = probe(registry, f"{row['title']}\n\n{row['listing']}") | {"id": row["source"]}
        tiers["summits"].append(got)
        print(f"  summit  {row['title'][:34]:<34} "
              + "  ".join(f"{name} {got[name]}" for name in FIELDS))

    for raw in args.ours:
        bundle = json.loads(Path(raw).read_text(encoding="utf-8"))
        for key in ("draft", "listing"):
            if not bundle.get(key):
                continue
            page = f"{bundle.get('title') or ''}\n\n{bundle[key]}".strip()
            got = probe(registry, page) | {"id": f"{Path(raw).parent.name}:{key}"}
            tiers["ours"].append(got)
            print(f"  ours    {got['id'][:34]:<34} "
                  + "  ".join(f"{name} {got[name]}" for name in FIELDS))

    report: dict[str, Any] = {"fields": list(FIELDS), "tiers": {}}
    for name, rows in tiers.items():
        report["tiers"][name] = {
            "n": len(rows),
            **{
                field: {
                    "interval": band([float(r[field]) for r in rows]),
                    "counts": [r[field] for r in rows],
                }
                for field in FIELDS
            },
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    # The quoted spans are text from published blurbs, so they go to derived/, never results/.
    (DERIVED / f"{args.out.stem}-spans.json").write_text(
        json.dumps(tiers, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print()
    for field in FIELDS:
        low, mean, high = report["tiers"]["ours"][field]["interval"]
        slow, smean, shigh = report["tiers"]["summits"][field]["interval"]
        verdict = (
            "OURS WORSE, disjoint" if low > shigh
            else "summits worse, disjoint" if slow > high
            else "overlap - blind"
        )
        print(f"  {field:14} ours {mean:5} [{low}, {high}]   "
              f"summits {smean:5} [{slow}, {shigh}]   {verdict}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
