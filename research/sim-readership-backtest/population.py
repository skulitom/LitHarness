"""The persona population: ten frozen readers, their prompts, and the reward/holdout split.

PREREG.md §6 is the contract. These are **parameterised tastes, not backstories** — the §70
lesson: a demographically described persona elicits stereotype performance, while a persona
described by what it reads and what makes it put a book down is constrained by something
checkable. Every axis here is explicit, every value frozen, and the whole table is
content-addressed so a result file can prove which population produced it.

The split precedes everything (the reader-judge-loop's I1 discipline): each persona lands in
the reward split or the holdout split by content hash of its id under the registered salt —
deterministic, non-re-rollable, computed rather than chosen. Only the reward split's aggregate
decides qualification; the holdout split is never a reward model and exists for later Goodhart
detection.

No model call, no I/O, no clock. `arms.py` renders these prompts into sessions; nothing here
decides what runs.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from hashlib import sha256

#: PREREG §6's registered salt. Changing it is changing which personas may become the reward
#: model, which is a new registration, not an edit.
SALT = "sim-backtest-v0-2026-08-24"

#: How many personas the reward split holds; the rest are holdout.
REWARD_SIZE = 6

#: The genre families personas hold priors over — the corpus's matching families plus the
#: catch-all, in one fixed order so the prior tuple is comparable across personas.
GENRE_FAMILIES: tuple[str, ...] = (
    "LitRPG",
    "Progression",
    "Portal Fantasy / Isekai",
    "High Fantasy",
    "Sci-fi",
    "other",
)


@dataclass(frozen=True, slots=True)
class Persona:
    """One reader, as parameters. Axes per PREREG §6; every value in [0, 1] unless typed.

    `genre_priors` aligns with `GENRE_FAMILIES` (a weight per family, higher = more at home).
    `slow_start_tolerance`: 0 = drops a slow opening fast, 1 = happily reads three quiet
    chapters. `progression_payoff_appetite`: how much visible advancement the reader needs to
    stay. `prose_register_preference`: the register that reads as home. `trope_familiarity
    _appetite`: 1 = wants the genre's furniture delivered straight, 0 = tired of it.
    """

    persona_id: str
    genre_priors: tuple[float, float, float, float, float, float]
    slow_start_tolerance: float
    progression_payoff_appetite: float
    prose_register_preference: str  # "plain" | "lyrical" | "either"
    trope_familiarity_appetite: float


#: The frozen population. Ten readers spread deliberately across the axes: heavy genre
#: loyalists, cross-genre generalists, register-sensitive and register-blind, patient and
#: impatient, trope-hungry and trope-tired. Authored 2026-08-24 with the registration;
#: `population_digest()` is the proof of exactly this table.
POPULATION: tuple[Persona, ...] = (
    Persona("grinder", (0.9, 0.8, 0.5, 0.3, 0.2, 0.2), 0.2, 0.95, "plain", 0.9),
    Persona("numbers", (0.95, 0.7, 0.4, 0.2, 0.4, 0.1), 0.35, 0.9, "plain", 0.8),
    Persona("comfort", (0.5, 0.5, 0.9, 0.5, 0.2, 0.4), 0.6, 0.5, "either", 0.85),
    Persona("wanderer", (0.3, 0.4, 0.6, 0.9, 0.3, 0.5), 0.85, 0.35, "lyrical", 0.5),
    Persona("crossover", (0.4, 0.5, 0.3, 0.4, 0.9, 0.4), 0.5, 0.6, "either", 0.4),
    Persona("stylist", (0.2, 0.3, 0.4, 0.7, 0.5, 0.6), 0.7, 0.3, "lyrical", 0.25),
    Persona("novelty", (0.5, 0.6, 0.5, 0.5, 0.6, 0.6), 0.45, 0.55, "either", 0.1),
    Persona("slowburn", (0.4, 0.6, 0.5, 0.8, 0.4, 0.5), 0.95, 0.4, "either", 0.6),
    Persona("skimmer", (0.7, 0.7, 0.6, 0.3, 0.4, 0.3), 0.1, 0.8, "plain", 0.45),
    Persona("omnivore", (0.6, 0.6, 0.6, 0.6, 0.6, 0.6), 0.5, 0.5, "either", 0.5),
)


def population_digest() -> str:
    """Content address of the frozen table, printed in every result file."""
    material = json.dumps([asdict(p) for p in POPULATION], sort_keys=True, ensure_ascii=False)
    return sha256(material.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------------------------------ the split


def _rank_key(persona_id: str) -> str:
    return sha256(f"{SALT}|{persona_id}".encode()).hexdigest()


def split_of(persona_id: str) -> str:
    """"reward" or "holdout", by content hash under the registered salt.

    The ten ids are ranked by their salted hash; the lowest `REWARD_SIZE` are the reward
    split. Deterministic and non-re-rollable: an operator who dislikes an assignment cannot
    re-roll it, and "why is this persona in this split" is arithmetic anyone can repeat.
    """
    known = {p.persona_id for p in POPULATION}
    if persona_id not in known:
        raise ValueError(f"unknown persona {persona_id!r}")
    ranked = sorted(known, key=_rank_key)
    return "reward" if persona_id in ranked[:REWARD_SIZE] else "holdout"


def reward_split() -> tuple[Persona, ...]:
    return tuple(p for p in POPULATION if split_of(p.persona_id) == "reward")


def holdout_split() -> tuple[Persona, ...]:
    return tuple(p for p in POPULATION if split_of(p.persona_id) == "holdout")


# ------------------------------------------------------------------------------------ prompts

#: The taste sentences, rendered from parameters. Byte-stable given the frozen table:
#: T0's A4 put roughly fourteen points of a verdict on wording, so the renderer is part of the
#: instrument. Reading-for-pleasure frame, an explicit right to walk away, and no quality
#: vocabulary anywhere — the persona reports behaviour, never a verdict.

_REGISTER_SENTENCE = {
    "plain": "You want prose that gets out of the way; showy writing makes you restless.",
    "lyrical": "You savour prose with texture, and flat utilitarian writing wears on you.",
    "either": "Prose style barely registers for you unless it trips you.",
}


def _band(value: float, low: str, mid: str, high: str) -> str:
    if value < 0.34:
        return low
    if value < 0.67:
        return mid
    return high


def system_prompt(persona: Persona) -> str:
    """The persona's system block: taste as reading behaviour, no verdict vocabulary."""
    favourites = [
        family
        for family, weight in zip(GENRE_FAMILIES, persona.genre_priors, strict=True)
        if weight >= 0.7
    ]
    at_home = (
        f"You are most at home in {', '.join(favourites)}."
        if favourites
        else "No genre owns you; you read across all of them."
    )
    patience = _band(
        persona.slow_start_tolerance,
        "A slow opening loses you within a chapter.",
        "You give a slow opening a chapter or two before drifting off.",
        "You will sit with a quiet opening for a long time if something is alive in it.",
    )
    payoff = _band(
        persona.progression_payoff_appetite,
        "Visible advancement matters little to you; you stay for other things.",
        "You like feeling the protagonist get somewhere, without needing it every chapter.",
        "You read for advancement you can feel; chapters where nobody gets anywhere lose you.",
    )
    tropes = _band(
        persona.trope_familiarity_appetite,
        "The genre's standard furniture bores you; you stay only for something you have "
        "not seen before.",
        "Familiar shapes are fine when they are done with conviction.",
        "You love the genre's furniture and want it delivered straight.",
    )
    return (
        "You read serialised web fiction for pleasure, hours of it a week, and you abandon "
        "most of what you start. Nobody is grading these books and neither are you: the only "
        "question you ever answer is what you would keep reading with your own limited time.\n"
        f"{at_home} {patience} {payoff} "
        f"{_REGISTER_SENTENCE[persona.prose_register_preference]} {tropes}\n"
        "Walking away from both books on offer is always allowed and often the truth."
    )
