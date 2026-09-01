"""One table from the pair result files, for the findings and the ledger: counts, never text.

`run.py` writes `summary.json` only when a whole plan completes; a run stopped once its controls
had answered has pair files and no summary. This reads every `pair-*.json` under a results
folder and prints the same numbers per pair — decided, file A, file B, neither, the first-slot
share in slot space and per order, the reason codes — sorted by kind so the controls and the
calibration pairs sit together. Nothing here calls a model or reads a stimulus.

    uv run python research/opening-parity/tabulate.py research/opening-parity/results/opening
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

KIND_ORDER = (
    "control-vs-source",
    "control-vs-summit",
    "summit-vs-summit",
    "ours-vs-ours",
    "ours-vs-summit",
    "control-vs-control",
)


def rows(folder: Path) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for path in sorted(folder.glob("pair-*.json")):
        r = json.loads(path.read_text(encoding="utf-8"))
        a = r["shares"]["aggregate"]
        p = r["positional"]
        out.append(
            {
                "kind": r["pair"]["kind"],
                "file_a": r["pair"]["file_a"],
                "file_b": r["pair"]["file_b"],
                "decided": a["decided"],
                "a": a["file_a"],
                "b": a["file_b"],
                "neither": a["neither"],
                "first_slot": p["first_slot_share"],
                "order0": p["by_order"]["0"]["first_slot_share"],
                "order1": p["by_order"]["1"]["first_slot_share"],
                "reasons": {k: v for k, v in r["reason_codes"]["counts"].items() if v},
                "failures": r["sessions"].get("transport_failures"),
            }
        )
    out.sort(key=lambda row: (KIND_ORDER.index(str(row["kind"])), str(row["file_a"])))
    return out


def markdown(table: list[dict[str, object]]) -> str:
    lines = [
        "| kind | file A | file B | decided | A | B | neither | first-slot | order 0 / 1 "
        "| reasons |",
        "| --- | --- | --- | --: | --: | --: | --: | --: | --: | --- |",
    ]
    for row in table:
        reasons = ", ".join(f"{k or '(none)'} {v}" for k, v in dict(row["reasons"]).items())
        lines.append(
            f"| {row['kind']} | {row['file_a']} | {row['file_b']} | {row['decided']} | "
            f"{row['a']} | {row['b']} | {row['neither']} | {row['first_slot']:.2f} | "
            f"{row['order0']:.1f} / {row['order1']:.1f} | {reasons} |"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    folder = Path(args[0]) if args else Path("research/opening-parity/results/opening")
    table = rows(folder)
    print(markdown(table))
    print(f"\n{len(table)} pair(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
