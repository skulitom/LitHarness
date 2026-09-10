"""Build repeatable creative briefs from a versioned deck, without calling a model.

The seed controls the brief, not the model's sampler or exact returned prose. Distinct
positions in one deck have distinct ingredient combinations; neither novelty nor quality
of the resulting stories is guaranteed. No model ranks or selects these combinations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

VERSION = "invention-ingredients.v1"
# This deliberately small, authored adventure palette is an experimental input mechanism,
# not a representative genre distribution or a permanent limit on story possibilities.
PALETTE = {
    "protagonist": (
        "a goblin youth impersonating a celebrated human champion",
        "a disgraced duelist returning under an enemy's identity",
        "a human newly trapped in the body of a hunted monster",
        "an exiled dragon whelp whose siblings want the same inheritance",
        "a runaway heir travelling with the person hired to capture them",
        "a reckless smuggler who has stolen something alive",
        "a pilgrim whose supposed holy destination is hunting them",
        "a defeated warlord forced to begin again at the lowest level",
    ),
    "world": (
        "a desert where colossal mirrors expose different inhabited worlds at dusk",
        "a forest migrating across the backs of rival sleeping beasts",
        "an archipelago where islands exchange their locations during eclipses",
        "rival kingdoms inside the fossilized skull of a dead god",
        "night markets connected through the nightmares of an unknown sleeper",
        "mountain citadels orbiting a star that casts solid shadows",
        "a glacier containing successive eras that can be entered through crevasses",
        "a buried empire whose roots grow upward into the present world's battlefields",
    ),
    "opening_engine": (
        "a competitive hunt in which the quarry recognizes the protagonist",
        "a jailbreak during the prison's transformation into a living predator",
        "a heist whose intended victim offers a more dangerous counteroffer",
        "a public duel against someone the protagonist secretly needs alive",
        "an infiltration in which the assumed identity has an unfinished personal feud",
        "a race through a migrating monster herd to reach a forbidden destination",
        "a siege in which the protagonist begins on the losing side",
        "a race to craft and wield an untested weapon before a public trial",
    ),
    "power": (
        "consume defeated monsters' organs to acquire traits that alter the user's body",
        "give stolen shadows physical form while their original owners can still command them",
        "grow stronger through narrowly survived defeats, retaining the injuries they caused",
        "turn witnessed lies into temporary creatures whose behavior follows the lie",
        "trade future years of life for short bursts of overwhelming combat ability",
        "exchange places with a summoned rival who learns from every encounter",
        "copy an opponent's technique by surrendering a cherished skill of one's own",
        "carry abilities across reincarnations while each new body changes how they work",
    ),
    "personal_pursuit": (
        "humiliate a revered rival in front of the people who abandoned the protagonist",
        "recover a stolen memory that would reveal whether the protagonist deserved exile",
        "return home before the people there forget the protagonist ever existed",
        "free a loved companion who is choosing to remain with the enemy",
        "win a crown the protagonist once publicly swore to destroy",
        "conceal an old crime from a sibling who is about to become an ally",
        "surpass a beloved mentor whose greatest achievement was fraudulent",
        "find the true target of a revenge oath made before losing one's former identity",
    ),
}
COMBINATIONS = math.prod(len(options) for options in PALETTE.values())


def _number(seed: str, label: str) -> int:
    encoded = json.dumps([VERSION, seed, label], ensure_ascii=False).encode("utf-8")
    return int.from_bytes(hashlib.sha256(encoded).digest(), "big")


def packet(seed: str, index: int = 0) -> dict[str, Any]:
    """Permute the finite Cartesian deck so positions never repeat within one seed."""
    if not seed or not 0 <= index < COMBINATIONS:
        raise ValueError(f"Supply a non-empty seed and an index from 0 to {COMBINATIONS - 1}")
    offset = _number(seed, "offset") % COMBINATIONS
    stride = _number(seed, "stride") % COMBINATIONS
    while math.gcd(stride, COMBINATIONS) != 1:
        stride = (stride + 1) % COMBINATIONS
    combination = (offset + index * stride) % COMBINATIONS
    remaining = combination
    ingredients, selections = {}, {}
    for axis, options in PALETTE.items():
        remaining, choice = divmod(remaining, len(options))
        selections[axis] = choice
        ingredients[axis] = options[choice]
    brief = (
        "Create a LitRPG portal-fantasy, isekai, or system-apocalypse adventure using these "
        "starting ingredients. Give each a causal role in the proposal. Invent the names, "
        "characters, local culture, specific events and connections between the ingredients.\n"
        + "\n".join(
            f"{axis.replace('_', ' ').capitalize()}: {value}."
            for axis, value in ingredients.items()
        )
    )
    return {
        "version": VERSION,
        "seed": seed,
        "index": index,
        "combination": combination,
        "selections": selections,
        "ingredients": ingredients,
        "brief": brief,
        "brief_sha256": hashlib.sha256(brief.encode("utf-8")).hexdigest(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", required=True, help="A label controlling the ingredient deck")
    parser.add_argument("--start", type=int, default=0, help="First position within the deck")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--out", type=Path, help="Write .json receipts and .brief.txt inputs here")
    args = parser.parse_args(argv)
    try:
        if args.count < 1 or args.start < 0 or args.start + args.count > COMBINATIONS:
            raise ValueError(f"Requested positions must fit in the {COMBINATIONS}-item deck")
        packets = [packet(args.seed, i) for i in range(args.start, args.start + args.count)]
        if args.out is not None:
            writes = {}
            for item in packets:
                prefix = args.out / f"seed-{item['index']:05d}"
                writes[prefix.with_suffix(".json")] = json.dumps(item, ensure_ascii=False, indent=2)
                writes[prefix.with_suffix(".brief.txt")] = item["brief"]
            if any(p.exists() for p in writes):
                raise ValueError("An output already exists; choose another directory or --start")
            args.out.mkdir(parents=True, exist_ok=True)
            for path, value in writes.items():
                with path.open("x", encoding="utf-8", newline="\n") as stream:
                    stream.write(value + "\n")
            print(json.dumps({"version": VERSION, "files": [str(p) for p in writes]}, indent=2))
        else:
            print(json.dumps(packets, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as error:
        print(json.dumps({"error": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
