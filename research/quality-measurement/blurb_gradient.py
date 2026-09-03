"""Can this readership tell a 12,000-follower serial from a 2-follower one, by blurb alone?

**This is the question underneath the operator's proposal**, 2026-08-26: *"if we can configure
readers to treat our overviews as close to 0/16 and top performing RR as 15/16 then we know we
found the correct initial baseline."* Right in principle, and it has a precondition nobody has
checked: **the readers must be able to read performance off a listing in the first place.**
Configuring them to separate ours from the market's best only means something if "the market's
best" is a class they can recognise without being told which side it is.

So this runs the same pairing with **both sides published** and an external label on each:

- HIGH — the top of the admitted pool by followers, thousands each.
- LOW — genre-tagged fictions with 25 followers or fewer, median 2, from the same shards.

**Length is matched pair by pair**, because a readership that picks the longer blurb every time
would produce a clean-looking gradient that is about word count. Nothing else is matched, and
the things that are not — cover, tags, rank, cadence, chapter one — are the reason a follower
count is only a *label* on a book and never a measurement of its blurb.

### The readings, fixed before the run

Let **H** be the share of decided pairs choosing the HIGH side.

| | reading |
| --- | --- |
| H >= 0.70 | the readership reads performance off a blurb. The operator's
  baseline is buildable and §140's 15/16 becomes interpretable. |
| 0.40 <= H <= 0.60 | it cannot. The pool's own top and bottom are one class to
  it, so no configuration built on this pool separates quality, and the 15/16
  says nothing about our listings either. |
| H <= 0.30 | it prefers the unsuccessful. A second inversion, and the strongest
  available statement that this pairing measures something other than what the
  market rewards. |
| position | void if the HIGH-first share is outside 0.40-0.60 pooled, or the two
  conditional rates differ by more than 0.15. Checked first. |

Anything between 0.30 and 0.40, or 0.60 and 0.70, is **no reading**: the bands are deliberately
not exhaustive so that an ambiguous result is reported as ambiguous rather than rounded to the
nearest story.

**Nothing here is tuned.** The roster and the question are `application/readers.py`'s, unchanged.
This measures the instrument that exists.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "src"))

from litharness.application import readers as readers_mod  # noqa: E402
from litharness.domain import rivals as rivals_mod  # noqa: E402
from litharness.packs import litrpg as litrpg_pack  # noqa: E402
from litharness.providers import build_default_registry  # noqa: E402

DERIVED = HERE / "derived"
RESULTS = HERE / "results"


def page(row: dict[str, Any]) -> str:
    return f"{row['title'].strip()}\n\n{row['listing'].strip()}"


def matched_pairs(high: list[dict[str, Any]], low: list[dict[str, Any]], count: int) -> list[
    tuple[dict[str, Any], dict[str, Any]]
]:
    """Each HIGH paired with the nearest unused LOW by word count. Length cannot be the tell."""
    ranked = sorted(high, key=lambda row: -int(row["followers"] or 0))[:count]
    spare = list(low)
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for top in ranked:
        want = len(top["listing"].split())
        spare.sort(key=lambda row: abs(len(row["listing"].split()) - want))
        if not spare:
            break
        pairs.append((top, spare.pop(0)))
    return pairs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--high", default=str(DERIVED / "rivals.json"))
    parser.add_argument("--low", default=str(DERIVED / "rivals-low.json"))
    parser.add_argument("--pairs", type=int, default=8)
    parser.add_argument("--out", type=Path, default=RESULTS / "blurb-gradient.json")
    parser.add_argument("--blind", action="store_true", help="use `packs.litrpg.BLIND`")
    args = parser.parse_args(argv)

    high = json.loads(Path(args.high).read_text(encoding="utf-8"))
    low = json.loads(Path(args.low).read_text(encoding="utf-8"))
    pairs = matched_pairs(high, low, args.pairs)
    registry = build_default_registry()
    seats = (
        litrpg_pack.BLIND if args.blind else litrpg_pack.pool(readers_mod.MEASUREMENT)
    )
    print(f"{len(pairs)} matched pair(s), HIGH from {len(high)}, LOW from {len(low)}")

    rows: list[dict[str, Any]] = []
    for index, (top, bottom) in enumerate(pairs):
        for reader in seats:
            seat = f"gradient|{index}|{reader.reader_id}"
            high_first = rivals_mod.ours_first(seat)
            request = readers_mod.render_pick_request(
                reader, page(top), page(bottom), high_first
            )
            try:
                result, _ = registry.complete(request)
            except Exception as error:  # an outage is a fact about the day
                rows.append({"pair": index, "refusal": str(error)[:160]})
                continue
            parsed = result.parsed if isinstance(result.parsed, dict) else {}
            rows.append(
                {
                    "pair": index,
                    "reader": reader.reader_id,
                    # `side_of` un-blinds against the recorded order; "ours" is the HIGH side.
                    "chose": readers_mod.side_of(str(parsed.get("next") or ""), high_first),
                    "high_first": high_first,
                    "high": top["source"],
                    "high_followers": top["followers"],
                    "low": bottom["source"],
                    "low_followers": bottom["followers"],
                    "high_words": len(top["listing"].split()),
                    "low_words": len(bottom["listing"].split()),
                    "because": str(parsed.get("because") or "").strip(),
                }
            )
        got = [r for r in rows if r.get("pair") == index and "chose" in r]
        picked = sum(1 for r in got if r["chose"] == "ours")
        print(f"  pair {index}: HIGH {picked}/{len(got)}  "
              f"({top['followers']} vs {bottom['followers']} followers, "
              f"{len(top['listing'].split())}w vs {len(bottom['listing'].split())}w)")

    answered = [r for r in rows if "chose" in r]
    decided = [r for r in answered if r["chose"] in {"ours", "theirs"}]
    counts = Counter(r["chose"] for r in answered)
    H = sum(r["chose"] == "ours" for r in decided) / len(decided) if decided else None
    first = [r for r in decided if r["high_first"]]
    second = [r for r in decided if not r["high_first"]]

    def share(subset: list[dict[str, Any]]) -> float | None:
        return sum(r["chose"] == "ours" for r in subset) / len(subset) if subset else None

    report = {
        "pairs": len(pairs),
        "answered": len(answered),
        "high": counts["ours"],
        "low": counts["theirs"],
        "neither": counts["neither"],
        "H": H,
        "high_first_share": len(first) / len(decided) if decided else None,
        "H_high_first": share(first),
        "H_high_second": share(second),
        # Counts only; the reasons quote published blurbs and go to derived/.
        "rows": [{k: v for k, v in r.items() if k != "because"} for r in rows],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (DERIVED / f"{args.out.stem}-reasons.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nHIGH {report['high']}  LOW {report['low']}  neither {report['neither']}   H={H}")
    print(f"  position: HIGH first in {report['high_first_share']}; "
          f"H|high-first {report['H_high_first']}  H|high-second {report['H_high_second']}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
