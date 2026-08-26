"""Put a listing beside a published one and see which the readership spends its slot on.

`plan/reader-calibration.md` is the registration and this is the runner. Read that first: the
readings K1-K4 are fixed there, the two ways this becomes circular are named there, and nothing
here may be interpreted outside it.

**What it does.** Every text under test is paired with rivals drawn from the admitted pool, one
per reader, unlabelled and order-swapped, and the four measurement readers each spend one slot.
`W` is the share of answered pairs that chose ours.

**The sham arm is what makes W readable.** A rival against another rival should split near even;
if the readership picks a side there, the pairing is measuring position or length or freshness
rather than anything about the writing, and our own W means nothing. It runs by default and its
cost is four calls a pair.

    uv run python research/quality-measurement/listing_arena.py \\
        --rivals derived/rivals.json --texts pilot7/listing.json pilot9/listing.json

The package interpreter, because this reads no corpus: the pool arrives as a file that
`rival_pool.py` wrote.

**Prose in, numbers out.** The results file carries counts, digests and the readers' one-line
reasons; it does not carry any listing, ours or anybody else's.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from hashlib import sha256
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "src"))

from litharness.application import readers as readers_mod  # noqa: E402
from litharness.domain import rivals as rivals_mod  # noqa: E402
from litharness.providers import build_default_registry  # noqa: E402

RESULTS = HERE / "results"
DERIVED = HERE / "derived"


def load_texts(paths: list[str]) -> list[dict[str, str]]:
    """Every text under test, as `{name, title, listing}`.

    A `listing.json` bundle contributes **two** entries — the draft and the revision — because
    the difference between them is the reader channel's own effect and the run gets it free.
    A `.txt` file contributes one, named by its stem.
    """
    out: list[dict[str, str]] = []
    for raw in paths:
        path = Path(raw)
        if path.suffix == ".json":
            bundle = json.loads(path.read_text(encoding="utf-8"))
            stem = path.parent.name
            for key, label in (("draft", "draft"), ("listing", "revised")):
                if bundle.get(key):
                    out.append(
                        {
                            "name": f"{stem}:{label}",
                            "title": bundle.get("title") or "",
                            "listing": bundle[key],
                        }
                    )
        else:
            out.append({"name": path.stem, "title": "", "listing": path.read_text("utf-8")})
    return out


def digest_of(text: str) -> str:
    return sha256(text.encode()).hexdigest()[:12]


def _page(entry: dict[str, str]) -> str:
    title = entry.get("title", "").strip()
    return f"{title}\n\n{entry['listing'].strip()}" if title else entry["listing"].strip()


def run_pair(
    registry: Any,
    ours: str,
    rival: rivals_mod.Rival,
    key: str,
    seats: tuple[readers_mod.Reader, ...],
) -> list[dict[str, Any]]:
    """Four readers, one text, one rival apiece. Returns a row per reader that answered."""
    rows: list[dict[str, Any]] = []
    for reader in seats:
        seat = f"{key}|{reader.reader_id}"
        first = rivals_mod.ours_first(seat)
        request = readers_mod.render_pick_request(reader, ours, rival.render(), first)
        try:
            result, _ = registry.complete(request)
        except Exception as error:  # an outage is a fact about the day, not about the text
            rows.append({"reader": reader.reader_id, "refusal": str(error)[:160]})
            continue
        parsed = result.parsed if isinstance(result.parsed, dict) else {}
        rows.append(
            {
                "reader": reader.reader_id,
                "chose": readers_mod.side_of(str(parsed.get("next") or ""), first),
                "ours_first": first,
                "rival": rival.source,
                "because": str(parsed.get("because") or "").strip(),
            }
        )
    return rows


def tally(rows: list[dict[str, Any]]) -> dict[str, Any]:
    answered = [row for row in rows if "chose" in row]
    counts = Counter(row["chose"] for row in answered)
    ours_first = [row for row in answered if row["ours_first"]]
    theirs_first = [row for row in answered if not row["ours_first"]]

    def share(subset: list[dict[str, Any]]) -> float | None:
        decided = [row for row in subset if row["chose"] in {"ours", "theirs"}]
        return sum(row["chose"] == "ours" for row in decided) / len(decided) if decided else None

    return {
        "answered": len(answered),
        "refused": len(rows) - len(answered),
        "ours": counts["ours"],
        "theirs": counts["theirs"],
        "neither": counts["neither"],
        "W": share(answered),
        "W_ours_first": share(ours_first),
        "W_theirs_first": share(theirs_first),
        "ours_first_share": len(ours_first) / len(answered) if answered else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rivals", required=True)
    parser.add_argument("--texts", nargs="+", required=True)
    parser.add_argument("--sham", type=int, default=4, help="rival-vs-rival pairs; 0 to skip")
    parser.add_argument("--out", type=Path, default=RESULTS / "listing-arena.json")
    parser.add_argument("--label", default="calibration")
    parser.add_argument(
        "--blind",
        action="store_true",
        help="use `readers.BLIND` — the measurement roster with no declared taste. The arm; "
        "`READERS` is its control",
    )
    args = parser.parse_args(argv)

    pool = rivals_mod.admit_all(json.loads(Path(args.rivals).read_text(encoding="utf-8")))
    texts = load_texts(args.texts)
    registry = build_default_registry()
    seats = (
        readers_mod.BLIND if args.blind else readers_mod.pool(readers_mod.MEASUREMENT)
    )
    print(f"{len(texts)} text(s) against a pool of {len(pool)}; sham pairs {args.sham}")

    ours_rows: list[dict[str, Any]] = []
    per_text: list[dict[str, Any]] = []
    for entry in texts:
        key = f"{args.label}|{entry['name']}"
        rows: list[dict[str, Any]] = []
        for reader in seats:
            seat = f"{key}|{reader.reader_id}"
            drawn = rivals_mod.draw(pool, seat)
            rows.extend(run_pair(registry, _page(entry), drawn, seat, seats)[:1])
        for row in rows:
            row["text"] = entry["name"]
        ours_rows.extend(rows)
        per_text.append(
            {"text": entry["name"], "digest": digest_of(entry["listing"])} | tally(rows)
        )
        got = per_text[-1]
        print(f"  {entry['name']:24} ours {got['ours']}/{got['answered']}  W={got['W']}")

    sham_rows: list[dict[str, Any]] = []
    for index in range(args.sham):
        # A rival stands in for "ours" against a different rival. Even-ish is the pass.
        left = pool[(index * 7 + 1) % len(pool)]
        right = pool[(index * 13 + 5) % len(pool)]
        if left.rival_id == right.rival_id:
            continue
        key = f"{args.label}|sham{index}"
        for reader in seats:
            seat = f"{key}|{reader.reader_id}"
            sham_rows.extend(run_pair(registry, left.render(), right, seat, seats)[:1])
    sham = tally(sham_rows) if sham_rows else None
    if sham:
        print(f"  {'SHAM published-v-published':24} ours {sham['ours']}/{sham['answered']}"
              f"  W={sham['W']}")

    every = ours_rows + [row | {"text": "sham"} for row in sham_rows]
    report = {
        "label": args.label,
        "pool": len(pool),
        "per_text": per_text,
        "pooled": tally(ours_rows),
        "sham": sham,
        # **Counts and choices, and no `because`.** A reader's reason quotes the blurb it just
        # read, and half the blurbs here are somebody else's published work — so the reasons go
        # to `derived/`, which `.gitignore` covers for exactly that, and `results/` keeps what
        # may be committed. `.gitignore`'s own note on the force programme states the rule:
        # the committed record carries ids, digests and numbers and no prose.
        "rows": [
            {key: value for key, value in row.items() if key != "because"} for row in every
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    reasons = DERIVED / f"{args.out.stem}-reasons.json"
    reasons.parent.mkdir(parents=True, exist_ok=True)
    reasons.write_text(json.dumps(every, ensure_ascii=False, indent=2), encoding="utf-8")
    pooled = report["pooled"]
    print(f"\npooled  ours {pooled['ours']}  theirs {pooled['theirs']}  "
          f"neither {pooled['neither']}  W={pooled['W']}")
    print(f"  position: ours first in {pooled['ours_first_share']}; "
          f"W|ours-first {pooled['W_ours_first']}  W|theirs-first {pooled['W_theirs_first']}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
