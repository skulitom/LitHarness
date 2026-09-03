"""Two declared systems, one printing the line: the drafting arms read the one the person stands in.

Stage-0 §197's second half. Until the concept stage every arm in `domain/extraction.py` asked
for exactly one declared system and abstained on two. A book whose person comes under a second
system after a turn declares two, and the one they stand in is the one whose columns the printed
line has — `_system_prints_the_line`'s own test, applied to each. That is a fact about the
book's line and not a preference among candidates (§61(5)): two systems that both print it are
still two answers, and the arms abstain as they always did.

No model call, no store. The fixture is `tests/test_choice_points.py`'s system with a second,
differently named system beside it.
"""

from __future__ import annotations

import litharness_contracts as lc

from litharness.domain import extraction, gamesystem
from tests.helpers import accepted as _accepted


def _weave() -> gamesystem.SystemDef:
    return gamesystem.SystemDef(
        system_id="sys_weave",
        name="the Weave",
        criterion="crit_seal",
        rank_label="Seal",
        ranks=(
            gamesystem.Rank("r_first", "First"),
            gamesystem.Rank("r_second", "Second"),
            gamesystem.Rank("r_third", "Third"),
        ),
        abilities=(
            gamesystem.Ability("cap_read", "Reading"),
            gamesystem.Ability("cap_pull", "Pull", needs=(gamesystem.Need("cap_read", 1),)),
            gamesystem.Ability("cap_slack", "Slack"),
            gamesystem.Ability("cap_kiln", "Kiln Hand"),
            gamesystem.Ability("cap_reed", "Reed Hand"),
        ),
        scale=gamesystem.Scale("Depth", 9),
        choices=(
            gamesystem.Choice(
                "fork_hand",
                "Hand",
                options=(
                    gamesystem.Option("opt_kiln", "Kiln", grants=("cap_kiln",)),
                    gamesystem.Option("opt_reed", "Reed", grants=("cap_reed",)),
                ),
                opens_at="r_second",
            ),
        ),
    )


def _accord() -> gamesystem.SystemDef:
    """The second system: its own ladder, its own grants, one of them the Weave's kept."""
    return gamesystem.SystemDef(
        system_id="sys_accord",
        name="the Accord",
        criterion="crit_bond",
        rank_label="Bond",
        ranks=(
            gamesystem.Rank("b_one", "One"),
            gamesystem.Rank("b_two", "Two"),
            gamesystem.Rank("b_three", "Three"),
        ),
        abilities=(
            gamesystem.Ability("cap_bargain", "Bargain"),
            gamesystem.Ability("cap_hold", "Hold", needs=(gamesystem.Need("cap_bargain", 1),)),
            gamesystem.Ability("cap_kept_read", "Reading"),
            gamesystem.Ability("cap_walk", "Walk"),
            gamesystem.Ability("cap_wait", "Wait"),
        ),
        scale=gamesystem.Scale("Depth", 9),
    )


def _canon(*, second: bool, second_prints: bool = False) -> list[lc.StateRecord]:
    """The Weave with Mira risen to its second rung, and optionally the Accord beside it.

    The Accord's own sheet is left out unless `second_prints`: a system the person has not come
    under yet prints nothing, which is what the seed is asked to declare (`_SECOND_SYSTEM`).
    """
    weave = _weave()
    risen = gamesystem.rise(gamesystem.starting_sheet(weave, "mira"), at="s2").sheet
    records = [*gamesystem.records_for(weave), *gamesystem.records_for_sheet(risen, at="s2")]
    if second:
        for record in gamesystem.records_for(_accord()):
            if record.predicate == extraction.SHEET_PREDICATE and not second_prints:
                continue
            records.append(record)
    return [_accepted(record) for record in records]


def test_one_declared_system_reads_as_it_always_did() -> None:
    canon = _canon(second=False)
    printing = extraction._printing_system(canon, canon)
    assert printing is not None and printing.system_id == "sys_weave"
    assert extraction.offered_choice(canon, character="mira", at="s3") == ("Hand", ("Kiln", "Reed"))


def test_two_declared_systems_and_the_one_printing_the_line_is_the_one_read() -> None:
    canon = _canon(second=True)
    assert [system.system_id for system in gamesystem.systems_of(canon)] == [
        "sys_accord",
        "sys_weave",
    ], "both systems are declared and read back"
    printing = extraction._printing_system(canon, canon)
    assert printing is not None and printing.system_id == "sys_weave"
    assert extraction.offered_choice(canon, character="mira", at="s3") == ("Hand", ("Kiln", "Reed"))
    assert extraction.offered_line(canon, character="mira", at="s3") is not None
    assert extraction.movable_names(canon, character="mira", at="s3")


def test_two_systems_both_declaring_a_sheet_print_the_one_the_person_stands_in() -> None:
    """Both systems declare a sheet, and the book's own snapshots settle which is live (§205):
    Mira stands in the Weave, so the Weave prints and the Accord does not. Before the default
    sheet retired, two declarations abstained to the default and neither printed, which the
    arms read as two answers; the answer is one, and it is the snapshot's."""
    canon = _canon(second=True, second_prints=True)
    printing = extraction._printing_system(canon, canon)
    assert printing is not None and printing.system_id == "sys_weave"
    assert extraction.offered_choice(canon, character="mira", at="s3") == ("Hand", ("Kiln", "Reed"))
    live = extraction.sheet_for(canon)
    assert live is not None and set(live.value_keys) == set(printing.value_keys)
