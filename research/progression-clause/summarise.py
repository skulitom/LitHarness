"""Read the ablation's saved prose and report the one statistic that separates the arms.

**Why this is a second script rather than a column in `ablate.py`'s table.** That table reports
`moved`, and `moved` turned out to be the wrong statistic: at the measured checkpoint the book's
own canon held `MP 6/4` — mana above its ceiling — so a draw that wrote `MP 4/4` scores as
"moved toward the milestone" when what it did was silently repair an impossible state. The MP
column is therefore uninterpretable, and any headline computed over all four mutable fields
inherits that.

**What separates the arms is whether the model computed a number at all.** Every value a draw
can write is either copied from one of the two status lines in front of it — the current state
and the milestone — or worked out from the events on the page. `novel` counts the second kind.
It needs no threshold, no calibration and no judgment call: a number is either printed in the
prompt or it is not.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from litharness.domain.extraction import STATUS_FIELDS, STATUS_PATTERN  # noqa: E402

MUTABLE = ("level", "hp", "mp", "gold")


def last_status(text: str) -> dict[str, int] | None:
    matches = list(STATUS_PATTERN.finditer(text or ""))
    if not matches:
        return None
    group = matches[-1].groupdict()
    return {field: int(group[field]) for field in STATUS_FIELDS}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prose", type=Path, required=True)
    parser.add_argument("--current", default="level=1,hp=15,mp=6,gold=25")
    parser.add_argument("--milestone", default="level=1,hp=5,mp=2,gold=30")
    args = parser.parse_args()

    current = {k: int(v) for k, v in (p.split("=") for p in args.current.split(","))}
    milestone = {k: int(v) for k, v in (p.split("=") for p in args.milestone.split(","))}

    groups: dict[tuple[str, str], list[dict[str, int] | None]] = defaultdict(list)
    words: dict[tuple[str, str], list[int]] = defaultdict(list)
    for path in sorted(glob.glob(str(args.prose / "*.txt"))):
        name = os.path.basename(path)[: -len(".txt")]
        tag, arm = name.split("-", 1)[0], name.split("-", 1)[1].rsplit("-", 1)[0]
        text = Path(path).read_text(encoding="utf-8")
        groups[(tag, arm)].append(last_status(text))
        words[(tag, arm)].append(len(text.split()))

    print(
        f"{'where':<7}{'arm':<15}{'n':>3}{'read':>6}{'gold':>6}{'hp':>5}"
        f"{'=stone':>8}{'NOVEL':>7}{'words':>7}"
    )
    for (tag, arm), rows in sorted(groups.items()):
        ok = [r for r in rows if r]
        novel = sum(
            1
            for r in ok
            for field in MUTABLE
            # A value is "novel" when it is neither the state the scene started from, nor the
            # milestone it was shown, nor either ceiling — i.e. it is not on the page anywhere.
            if r[field] not in {current[field], milestone[field], r["hp_max"], r["mp_max"]}
        )
        print(
            f"{tag:<7}{arm:<15}{len(rows):>3}{len(ok):>6}"
            f"{sum(1 for r in ok if r['gold'] != current['gold']):>6}"
            f"{sum(1 for r in ok if r['hp'] != current['hp']):>5}"
            f"{sum(1 for r in ok if all(r[f] == milestone[f] for f in ('hp', 'mp', 'gold'))):>8}"
            f"{novel:>7}"
            f"{sum(words[(tag, arm)]) // max(len(rows), 1):>7}"
        )
    print(
        "\nNOVEL counts field-writes that are not printed anywhere in the prompt. It is the "
        "column that\nseparates copying a status line from writing a state the scene earned."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
