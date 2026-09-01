"""The completion's bounds reach the Architect, and its refusal reaches the check.

Serial Pilot 19 (2026-09-01): the seed drew a coherent system with eleven abilities, `world
accept` refused to finish it — a drawn system carries five to eight, the width of a printed
line — and `world check` reported only that the system lacked a scale, which is true and is
not the reason. Two seams, pinned here: the seed's system sentence now states the bound in the
same words `gamesystem` enforces, and the check's unfinished-system sentence carries the
completion's own reason beside the symptom.

No model call, no store, no corpus.
"""

from __future__ import annotations

import pytest
from test_choice_points import _accepted, _system

from litharness.application import world_agent
from litharness.domain import gamesystem, genre, house

_NUMBER_WORDS = {5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}


def test_the_seed_states_the_ability_bound_the_completion_enforces() -> None:
    """One sentence, not two: the bound rides the grants sentence on a semicolon, so the
    Architect's demand count is what it was (`tests/test_prompt_budget.py` owns the ceiling).
    The words are pinned to the constants so a moved bound cannot leave a stale sentence."""
    low, high = _NUMBER_WORDS[gamesystem.MIN_ABILITIES], _NUMBER_WORDS[gamesystem.MAX_ABILITIES]
    assert f"no fewer than {low} grants and no more than {high}" in world_agent._SYSTEM
    assert "refused at acceptance" in world_agent._SYSTEM
    grants = [
        item for item in house.demands(world_agent._SYSTEM) if "Declare what the system" in item
    ]
    assert len(grants) == 1
    assert low in grants[0] and high in grants[0]


def test_the_check_carries_the_completion_s_reason_beside_the_missing_scale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A system one predicate short is reported as unfinished; when acceptance would refuse to
    finish it, the refusal's own sentence rides beside the symptom rather than being printed
    once at `world accept` and lost."""
    complete = [_accepted(record) for record in gamesystem.records_for(_system())]
    short = [record for record in complete if record.predicate != gamesystem.MAGNITUDE_SCALE]
    assert gamesystem.unfinished_systems(short), "the fixture must read as unfinished"

    gap = genre.system_gap(short)
    assert gap is not None
    assert gap.startswith("this book began a game system and did not finish it")
    # This fixture's deepest declared magnitude is one, under `MIN_SCALE_MAXIMUM`, so the
    # completion refuses it for depth and the check now says so where it used to say only
    # that the scale was missing.
    assert "Acceptance would not finish it either, and says why: sys_weave declares no depth" in gap
    assert gap.index("did not finish it") < gap.index("Acceptance would not")

    def refuse(records: object) -> tuple[tuple[()], tuple[str, ...]]:
        return (), ("sys_weave declares 11 abilities; a drawn system carries 5 to 8",)

    monkeypatch.setattr(genre.gamesystem_mod, "completion_records", refuse)
    refused = genre.system_gap(short)
    assert refused is not None
    assert "says why: sys_weave declares 11 abilities" in refused

    def finish(records: object) -> tuple[tuple[()], tuple[()]]:
        return (), ()

    monkeypatch.setattr(genre.gamesystem_mod, "completion_records", finish)
    finished = genre.system_gap(short)
    assert finished is not None
    assert "Acceptance would not finish it" not in finished
