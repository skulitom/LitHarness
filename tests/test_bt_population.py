"""The frozen persona population, checked without calls.

What this file pins: the table's shape and freeze (digest stability), the content-derived
reward/holdout split (sizes, determinism, disjointness, non-re-rollability under the
registered salt), and the prompt renderer's rails — byte-stable output, taste rendered as
behaviour, an explicit right to abandon, and no verdict vocabulary anywhere. What it does not
establish: anything about how any model behaves under these prompts.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(
    0, str(Path(__file__).resolve().parent.parent / "research" / "sim-readership-backtest")
)
import pytest

population = pytest.importorskip("population", reason="research module; imported by path")

BANNED = re.compile(r"\b(quality|good|bad|rate|score|judge|evaluat\w*|assess\w*)\b", re.I)


def test_the_population_is_ten_personas_with_unique_ids() -> None:
    ids = [p.persona_id for p in population.POPULATION]
    assert len(ids) == 10
    assert len(set(ids)) == 10


def test_every_parameter_sits_in_its_registered_range() -> None:
    for p in population.POPULATION:
        assert len(p.genre_priors) == len(population.GENRE_FAMILIES)
        for weight in p.genre_priors:
            assert 0.0 <= weight <= 1.0, p.persona_id
        assert 0.0 <= p.slow_start_tolerance <= 1.0
        assert 0.0 <= p.progression_payoff_appetite <= 1.0
        assert 0.0 <= p.trope_familiarity_appetite <= 1.0
        assert p.prose_register_preference in ("plain", "lyrical", "either")


def test_the_population_digest_is_stable_and_hex() -> None:
    digest = population.population_digest()
    assert digest == population.population_digest()
    assert len(digest) == 16
    int(digest, 16)


def test_the_split_is_six_reward_four_holdout_and_disjoint() -> None:
    reward = population.reward_split()
    holdout = population.holdout_split()
    assert len(reward) == population.REWARD_SIZE == 6
    assert len(holdout) == 4
    assert {p.persona_id for p in reward}.isdisjoint({p.persona_id for p in holdout})
    assert len(reward) + len(holdout) == len(population.POPULATION)


def test_the_split_is_deterministic_arithmetic_not_choice() -> None:
    """Anyone can repeat the assignment: rank the salted hashes, take the lowest six."""
    from hashlib import sha256

    ids = {p.persona_id for p in population.POPULATION}
    ranked = sorted(ids, key=lambda i: sha256(f"{population.SALT}|{i}".encode()).hexdigest())
    for persona_id in ids:
        expected = "reward" if persona_id in ranked[:6] else "holdout"
        assert population.split_of(persona_id) == expected


def test_an_unknown_persona_id_is_refused_by_name() -> None:
    with pytest.raises(ValueError, match="unknown persona"):
        population.split_of("stranger")


def test_prompts_are_byte_stable_and_distinct_across_personas() -> None:
    prompts = [population.system_prompt(p) for p in population.POPULATION]
    again = [population.system_prompt(p) for p in population.POPULATION]
    assert prompts == again
    assert len(set(prompts)) == len(prompts), "two personas rendered identical prompts"


def test_every_prompt_grants_the_right_to_abandon_and_bans_verdict_vocabulary() -> None:
    for p in population.POPULATION:
        prompt = population.system_prompt(p)
        assert "Walking away from both books" in prompt
        assert "for pleasure" in prompt
        match = BANNED.search(prompt)
        assert match is None, f"{p.persona_id}: verdict word {match.group(0)!r}"


def test_a_genre_loyalist_names_its_families_and_the_generalist_names_none() -> None:
    by_id = {p.persona_id: p for p in population.POPULATION}
    grinder = population.system_prompt(by_id["grinder"])
    assert "most at home in LitRPG, Progression" in grinder
    omnivore = population.system_prompt(by_id["omnivore"])
    assert "No genre owns you" in omnivore


def test_the_band_helper_switches_at_its_two_boundaries() -> None:
    assert population._band(0.33, "low", "mid", "high") == "low"
    assert population._band(0.34, "low", "mid", "high") == "mid"
    assert population._band(0.66, "low", "mid", "high") == "mid"
    assert population._band(0.67, "low", "mid", "high") == "high"
