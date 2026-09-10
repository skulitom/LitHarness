"""Reproducible creative inputs; entropy and persistence belong to the caller.

The finite authored palette is an input policy, not a novelty or quality guarantee.
The earlier standalone tool keeps its original experimental version unchanged.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

VERSION = "invention-seed.v1"
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
# The reward and further uses stay attached to the sampled opening activity.
ACTIVITIES = (
    (
        "outwit and catch an elusive creature before a rival hunter does",
        "track, stalk and outmaneuver more elusive quarry in unfamiliar territory",
    ),
    (
        "deceive an active captor and escape the prison's pursuit",
        "evade pursuit, infiltrate captivity and extract someone through active opposition",
    ),
    (
        "steal a closely guarded possession from an opponent who actively defends it",
        "conceal a theft, penetrate guarded places and turn a stolen advantage against its owner",
    ),
    (
        "defeat a rival in a public duel while keeping the opponent alive",
        "counter unfamiliar fighting styles and win against opponents who learn from earlier bouts",
    ),
    (
        "sustain an assumed identity under a suspicious enemy's direct examination",
        "impersonate, misdirect and manipulate enemies with conflicting loyalties",
    ),
    (
        "outpace a pursuing creature and enter the forbidden destination ahead of a rival",
        "race dangerous creatures and explore territory competitors cannot yet reach",
    ),
    (
        "ambush and capture an enemy commander needed alive for the personal pursuit",
        "ambush, outmaneuver and fight stronger opponents to advance the same pursuit",
    ),
    (
        "wield the newly made weapon to overcome an active opponent in the public trial",
        "invent and wield unfamiliar weapons against opponents who adapt to earlier designs",
    ),
)


@dataclass(frozen=True, slots=True)
class InventionSeed:
    """A retained input receipt; the label controls a brief, never the native sampler."""

    seed: str
    index: int
    version: str
    mode: str
    brief: str

    def __post_init__(self) -> None:
        for field in ("seed", "version", "mode", "brief"):
            if not isinstance(getattr(self, field), str) or not getattr(self, field).strip():
                raise ValueError(f"invention_seed.{field} must be non-empty text")
        if isinstance(self.index, bool) or not isinstance(self.index, int) or self.index < 0:
            raise ValueError("invention_seed.index must be a non-negative integer")

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "seed": self.seed,
            "index": self.index,
            "version": self.version,
            "mode": self.mode,
            "brief": self.brief,
            "brief_sha256": hashlib.sha256(self.brief.encode("utf-8")).hexdigest(),
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> InventionSeed:
        # Retain stored versions verbatim; a later palette cannot rewrite an older receipt.
        if not {"seed", "index", "version", "mode", "brief"} <= payload.keys():
            raise ValueError("invention_seed is missing its input receipt fields")
        value = cls(
            seed=payload["seed"],
            index=payload["index"],
            version=payload["version"],
            mode=payload["mode"],
            brief=payload["brief"],
        )
        if payload.get("brief_sha256") != value.to_jsonable()["brief_sha256"]:
            raise ValueError("invention_seed.brief_sha256 does not match the retained brief")
        return value


def make_seed(seed: str, index: int = 0, *, actions: bool = True) -> InventionSeed:
    """Take a deterministic position in a finite deck, optionally with activity guidance."""
    if not isinstance(seed, str) or not seed.strip():
        raise ValueError("Supply a non-empty invention seed")
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < COMBINATIONS:
        raise ValueError(f"Seed index must be from 0 to {COMBINATIONS - 1}")

    def number(label: str) -> int:
        value = json.dumps([VERSION, seed, label], ensure_ascii=False).encode("utf-8")
        return int.from_bytes(hashlib.sha256(value).digest(), "big")

    stride = number("stride") % COMBINATIONS
    while math.gcd(stride, COMBINATIONS) != 1:
        stride = (stride + 1) % COMBINATIONS
    remaining = (number("offset") + index * stride) % COMBINATIONS
    choices, ingredients = {}, {}
    for axis, options in PALETTE.items():
        remaining, choice = divmod(remaining, len(options))
        choices[axis] = choice
        ingredients[axis] = options[choice]
    brief = "\n".join(
        f"{axis.replace('_', ' ').capitalize()}: {value}." for axis, value in ingredients.items()
    )
    if actions:
        first, later = ACTIVITIES[choices["opening_engine"]]
        brief += (
            f"\nFirst magical success: use the first earned capability to {first}. "
            "Make this success yield something the protagonist can use toward the personal "
            "pursuit. Realize the chosen power's actual mechanism, with its limitation changing "
            "the action. Invent the specific technique and the connections between ingredients."
            f"\nFurther power growth: develop new ways to {later}. Describe a concrete later "
            "success in that activity and how an opponent or discovery makes the next use "
            "different. Keep the chosen power's mechanism central as its applications expand."
        )
    return InventionSeed(seed, index, VERSION, "actions" if actions else "ingredients", brief)
