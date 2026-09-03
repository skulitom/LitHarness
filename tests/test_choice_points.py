"""The fork a system offers, and the beat that puts the interface in somebody's hands.

**What read 10 named, in the machinery's own terms.** The operator, on serial pilot 15b draw 4 —
the draw the coordinator's gate passed — is that a rendered status line arriving at a number-move
reads as *noise*: a system that is never opened, read or weighed by anybody in the book is a
narrator's overlay whatever it prints. `plan/serial-pilot-15b.md` owns the quote and nothing of it
is in any prompt (§97.1). Two facts of the shipped contract produced it, neither a bug:

- §161.3 anchored the printed line to a **number-move**, which is an event in the machinery. Both
  of its placements are correct against the footer defect they were written for and neither
  involves a person.
- `gamesystem.SystemDef` modelled an ability graph, a named ladder and one magnitude scale and
  **no fork** — no moment where the system offers and somebody takes. The gap was already queued
  in `plan/house-genre-constraint.md`, with the operator's own awe direction beside it.

This file grades both halves and the seam between them: that a fork is declarable, coherent,
gating, irrevocable and readable back out of canon; that nothing anywhere ranks a way of taking
one; that the furniture's placement now starts with a person; that the interaction beat fires
where the design says and nowhere else; and that a system with no fork is byte-identical to what
it was, which is what makes all of it a ratchet rather than a migration.

No model call, no network, no store. `plan/diegetic-system-and-choice.md` is the design record.
"""

from __future__ import annotations

import inspect

import pytest

from litharness.domain import extraction, gamesystem, genre, house, worlds
from tests.helpers import accepted as _accepted


def _system(**overrides: object) -> gamesystem.SystemDef:
    """A five-ability system with one two-way fork opening at the middle rung.

    `cap_kiln` and `cap_reed` are what the fork gates; `cap_read`, `cap_pull` and `cap_slack` are
    the ordinary inventory, so the draw has openers, a prerequisite edge and a gate at once.
    """
    base: dict[str, object] = {
        "system_id": "sys_weave",
        "name": "the Weave",
        "criterion": "crit_seal",
        "rank_label": "Seal",
        "ranks": (
            gamesystem.Rank("r_first", "First"),
            gamesystem.Rank("r_second", "Second"),
            gamesystem.Rank("r_third", "Third"),
        ),
        "abilities": (
            gamesystem.Ability("cap_read", "Reading"),
            gamesystem.Ability("cap_pull", "Pull", needs=(gamesystem.Need("cap_read", 1),)),
            gamesystem.Ability("cap_slack", "Slack"),
            gamesystem.Ability("cap_kiln", "Kiln Hand"),
            gamesystem.Ability("cap_reed", "Reed Hand"),
        ),
        "scale": gamesystem.Scale("Depth", 9),
        "choices": (
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
    }
    base.update(overrides)
    return gamesystem.SystemDef(**base)  # type: ignore[arg-type]


def _forkless() -> gamesystem.SystemDef:
    """The same system with the fork taken out — the control every assertion below is read
    against, and the fixture the digest rail is pinned on."""
    return _system(choices=())


# --------------------------------------------------------------------------- the ratchet
#
# A system with no fork is the system it always was. These three are the whole reason §173 needed
# no migration, and they are asserted first because everything after them is only safe if they
# hold.


def test_a_system_with_no_fork_digests_exactly_as_it_always_did() -> None:
    """The literal is the digest this fixture produced under the code of 2026-08-29, before
    `SystemDef` had a `choices` field at all, computed by loading that revision of the module
    beside this one and comparing.

    **`SYSTEM_DIGEST` exists so that drift is a question a reader can ask** (§160). A schema
    addition that moved every existing system's digest would report a redefinition that never
    happened, on every sheet that cites one — the value lying in the one direction it was built to
    make impossible. So `digest` folds the forks into its material only when there are forks, and
    this is that promise with a number on it rather than an argument.
    """
    assert _forkless().digest == "sys-26dcad7f12d86f741130db33"


def test_a_system_with_no_fork_writes_exactly_the_records_it_always_wrote() -> None:
    """`records_for`'s fork block is skipped entirely, so a book already on disk reads back the
    same system out of the same canon."""
    written = worlds.granted_by(gamesystem.records_for(_forkless()), "opt_kiln")
    assert written == ()
    assert not [
        record
        for record in gamesystem.records_for(_forkless())
        if record.predicate in (worlds.OFFERS, worlds.GRANTS, worlds.CHOSE)
    ]


def test_a_sheet_with_no_pick_offers_what_it_always_offered() -> None:
    """`unlocked` answers True for every ungated ability, so `legal_moves` on a forkless system
    is what it was and a book written before forks existed selects identically."""
    sheet = gamesystem.starting_sheet(_forkless(), "mira")
    assert sheet.picks == ()
    assert all(sheet.unlocked(ability_id) for ability_id in _forkless().ability_ids)
    kinds = {move.kind for move in gamesystem.legal_moves(sheet)}
    assert gamesystem.AdvanceKind.CHOOSE not in kinds


# --------------------------------------------------------------------------- the gate


def test_a_gated_ability_is_not_offered_until_its_fork_is_taken() -> None:
    """The arithmetic that makes a fork a fork rather than a label.

    §161.4 records why the system arm of the beat vocabulary beats a column label: a label cannot
    know a move is unavailable, so a schedule built on one names moves the book cannot make. A
    fork is one more thing a label cannot know.
    """
    system = _system()
    sheet = gamesystem.starting_sheet(system, "mira")
    at_second = gamesystem.rise(sheet, at="s2").sheet
    offered = {move.ability_id for move in gamesystem.legal_moves(at_second)}
    assert "cap_kiln" not in offered and "cap_reed" not in offered

    taken = gamesystem.choose(at_second, "fork_hand", "opt_kiln", at="s3").sheet
    after = {move.ability_id for move in gamesystem.legal_moves(taken)}
    assert "cap_kiln" in after
    assert "cap_reed" not in after, "the way not taken stays shut, which is the foreclosure"


def test_a_gated_ability_is_never_an_opener() -> None:
    """A starting sheet holding what a fork gates would hand the character a branch they never
    took, and the reader a column that lit up before the choice existed."""
    sheet = gamesystem.starting_sheet(_system(), "mira")
    assert sheet.magnitude("cap_kiln") == 0 and sheet.magnitude("cap_reed") == 0
    assert sheet.magnitude("cap_read") == 1, "the ungated openers are unaffected"


def test_a_system_whose_every_ability_is_gated_has_no_starting_sheet() -> None:
    """And the complaint that fires is `check_draw`'s existing one, which is the right sentence
    for that draw rather than a new one about forks."""
    system = _system(
        abilities=(
            gamesystem.Ability("cap_a", "Alpha"),
            gamesystem.Ability("cap_b", "Beta", needs=(gamesystem.Need("cap_a", 1),)),
            gamesystem.Ability("cap_c", "Gamma"),
            gamesystem.Ability("cap_d", "Delta"),
            gamesystem.Ability("cap_e", "Epsilon"),
        ),
        choices=(
            gamesystem.Choice(
                "fork_all",
                "Hand",
                options=(
                    gamesystem.Option("opt_one", "One", grants=("cap_a", "cap_b")),
                    gamesystem.Option("opt_two", "Two", grants=("cap_c", "cap_d", "cap_e")),
                ),
            ),
        ),
    )
    complaints = gamesystem.check_draw(system)
    assert any("no ability can be held at the first rung" in c for c in complaints)


def test_the_unheld_ways_sit_on_the_line_at_nothing_where_the_reader_can_see_them() -> None:
    """The awe mechanism was already half-built and this is the half that finishes it.

    `columns` prints every declared ability including the ones nobody holds — §160 wrote that with
    the operator's *"i wonder what I would pick"* beside it — so a fork's grants are already
    visible at 0 from page one and exactly one branch will ever light up. Nothing new had to be
    rendered for a reader to be able to want one.
    """
    snapshot = gamesystem.starting_sheet(_system(), "mira").snapshot()
    assert snapshot["cap_kiln"] == 0 and snapshot["cap_reed"] == 0
    assert "Kiln Hand" in {column.label for column in _system().columns}


def test_a_pick_never_reaches_the_printed_line() -> None:
    """§160.3's split, held: the field pattern is digits only, so a taken way can no more ride a
    column than a rung's name can. §166.3 settled where it goes instead — the licence reaches
    numerals, so a name is governed by nothing in it."""
    system = _system()
    sheet = gamesystem.starting_sheet(system, "mira")
    at_second = gamesystem.rise(sheet, at="s2").sheet
    taken = gamesystem.choose(at_second, "fork_hand", "opt_kiln", at="s3").sheet
    assert taken.snapshot() == at_second.snapshot()
    assert "opt_kiln" not in str(taken.snapshot()) and "Kiln" not in str(taken.snapshot())


# --------------------------------------------------------------------------- taking one


def test_a_fork_opens_at_a_rung_and_not_at_a_story_position() -> None:
    """§110.3 measured position-implies-settlement failing in both directions inside one run, and
    §167 settled the same question for disclosure. A fork opens because the person got to the
    rung, which needs no story position at all and so cannot leak one."""
    system = _system()
    sheet = gamesystem.starting_sheet(system, "mira")
    assert gamesystem.pending_choices(sheet) == ()
    with pytest.raises(gamesystem.IllegalAdvance, match="opens at r_second"):
        gamesystem.choose(sheet, "fork_hand", "opt_kiln", at="s1")
    risen = gamesystem.rise(sheet, at="s2").sheet
    assert [choice.choice_id for choice in gamesystem.pending_choices(risen)] == ["fork_hand"]


def test_a_fork_is_taken_once_and_nothing_takes_it_back() -> None:
    """Foreclosure is the whole of what separates a choice from a checklist, and there is no
    `world retract` to undo a `chose` edge with (§160.5, still owed)."""
    system = _system()
    risen = gamesystem.rise(gamesystem.starting_sheet(system, "mira"), at="s2").sheet
    taken = gamesystem.choose(risen, "fork_hand", "opt_kiln", at="s3").sheet
    assert gamesystem.pending_choices(taken) == ()
    with pytest.raises(gamesystem.IllegalAdvance, match="already took opt_kiln"):
        gamesystem.choose(taken, "fork_hand", "opt_reed", at="s4")


def test_taking_a_fork_moves_no_number_and_writes_one_record() -> None:
    """A fork changes what is *possible*; the gain is still an advancement with its own position
    and its own beat. Granting three columns in one act would collapse the progression the
    schedule exists to spread out, which is the `progression` block's own argument.

    One record and no snapshot beside it: nothing moved, and `worlds.record_id_for` is
    position-blind under an `INSERT OR IGNORE` store, so the restatement §160 found being silently
    dropped would be dropped here too.
    """
    system = _system()
    risen = gamesystem.rise(gamesystem.starting_sheet(system, "mira"), at="s2").sheet
    advance = gamesystem.choose(risen, "fork_hand", "opt_kiln", at="s3")
    assert advance.kind is gamesystem.AdvanceKind.CHOOSE
    assert advance.moved == ()
    assert advance.before == advance.after
    assert [record.predicate for record in advance.records] == [worlds.CHOSE]
    written = advance.records[0]
    assert written.object_ref == "opt_kiln" and written.value == "fork_hand"


# --------------------------------------------------------------------------- reading it back


def test_a_drawn_fork_round_trips_through_canon_unchanged() -> None:
    """The digest is what says so, which is the stronger assertion: §160 caught a round trip that
    did not close by comparing objects rather than trusting one."""
    system = _system()
    read_back = gamesystem.systems_of(gamesystem.records_for(system))
    assert len(read_back) == 1
    assert read_back[0] == system
    assert read_back[0].digest == system.digest


def test_a_pick_is_read_back_off_its_own_edge_and_only_where_the_book_has_reached_it() -> None:
    """§165's two order-key spaces and §167's cutoff, on the sheet.

    A `chose` written in the schedule space is canon, readable, and never read as already taken
    from a scene — `'0350' <= 's1'` is `True` by spelling, and `state.comparable` is what stops
    that being an answer.
    """
    from litharness.domain import state as state_mod

    system = _system()
    risen = gamesystem.rise(gamesystem.starting_sheet(system, "mira"), at="s2").sheet
    scheduled = gamesystem.choose(risen, "fork_hand", "opt_kiln", at="0350")
    canon = [
        _accepted(record)
        for record in (
            *gamesystem.records_for(system),
            *gamesystem.records_for_sheet(risen),
            *scheduled.records,
        )
    ]
    assert state_mod.comparable("0350", "s1") is False

    here = gamesystem.sheet_of(canon, "mira", system=system, at="s1")
    assert here is not None
    assert here.picks == (), "a scheduled pick is not one the book has taken"
    everywhere = gamesystem.sheet_of(canon, "mira", system=system)
    assert everywhere is not None
    assert everywhere.picks == (("fork_hand", "opt_kiln"),)


# --------------------------------------------------------------------------- what a draw may be


@pytest.mark.parametrize(
    ("choices", "expected"),
    [
        pytest.param(
            (
                gamesystem.Choice(
                    "fork_hand",
                    "Hand",
                    options=(gamesystem.Option("opt_kiln", "Kiln", grants=("cap_kiln",)),),
                    opens_at="r_second",
                ),
            ),
            "offers 1 way",
            id="one way forecloses nothing",
        ),
        pytest.param(
            (
                gamesystem.Choice(
                    "fork_hand",
                    "Hand",
                    options=(
                        gamesystem.Option("opt_kiln", "Kiln", grants=("cap_kiln",)),
                        gamesystem.Option("opt_reed", "Reed"),
                    ),
                    opens_at="r_second",
                ),
            ),
            "opens nothing",
            id="a way that grants nothing",
        ),
        pytest.param(
            (
                gamesystem.Choice(
                    "fork_hand",
                    "Hand",
                    options=(
                        gamesystem.Option("opt_kiln", "Kiln", grants=("cap_kiln",)),
                        gamesystem.Option("opt_reed", "Reed", grants=("cap_kiln",)),
                    ),
                    opens_at="r_second",
                ),
            ),
            "two answers to whether it is locked",
            id="one ability behind two gates",
        ),
        pytest.param(
            (
                gamesystem.Choice(
                    "fork_hand",
                    "Hand",
                    options=(
                        gamesystem.Option("opt_kiln", "Kiln", grants=("cap_kiln",)),
                        gamesystem.Option("opt_reed", "Reed", grants=("cap_nothing",)),
                    ),
                    opens_at="r_second",
                ),
            ),
            "does not declare as an ability",
            id="a grant nothing declares",
        ),
        pytest.param(
            (
                gamesystem.Choice(
                    "fork_hand",
                    "Hand",
                    options=(
                        gamesystem.Option("opt_kiln", "Kiln", grants=("cap_kiln",)),
                        gamesystem.Option("opt_reed", "Reed", grants=("cap_reed",)),
                    ),
                    opens_at="r_nowhere",
                ),
            ),
            "which this system declares as no rung",
            id="opening at a rung nobody declared",
        ),
        pytest.param(
            (
                gamesystem.Choice(
                    "fork_hand",
                    "Hand 2",
                    options=(
                        gamesystem.Option("opt_kiln", "Kiln", grants=("cap_kiln",)),
                        gamesystem.Option("opt_reed", "Reed", grants=("cap_reed",)),
                    ),
                    opens_at="r_second",
                ),
            ),
            "cannot be put in a scene plan",
            id="a name with a digit in it",
        ),
    ],
)
def test_an_incoherent_fork_is_complained_about_in_the_terms_of_its_own_defect(
    choices: tuple[gamesystem.Choice, ...], expected: str
) -> None:
    """Every check is membership or arithmetic, exactly as `check_draw`'s others are.

    The name check is not decoration: a fork's name and its ways reach a scene plan as book data,
    which is text that shapes prose a reader reads, so they are held to `_printable_label`'s rule
    for the same reason a printed column label is.
    """
    complaints = " | ".join(gamesystem.check_draw(_system(choices=choices)))
    assert expected in complaints


def test_a_way_offered_by_two_forks_is_refused() -> None:
    """One way belongs to one fork, or taking it forecloses in two places at once."""
    system = _system(
        choices=(
            gamesystem.Choice(
                "fork_hand",
                "Hand",
                options=(
                    gamesystem.Option("opt_kiln", "Kiln", grants=("cap_kiln",)),
                    gamesystem.Option("opt_reed", "Reed", grants=("cap_reed",)),
                ),
            ),
            gamesystem.Choice(
                "fork_eye",
                "Eye",
                options=(
                    gamesystem.Option("opt_kiln", "Kiln", grants=("cap_slack",)),
                    gamesystem.Option("opt_far", "Far", grants=("cap_pull",)),
                ),
            ),
        )
    )
    assert any("is offered by fork_eye" in c or "is offered by fork_hand" in c
               for c in gamesystem.check_draw(system))


def test_a_coherent_fork_draws_clean() -> None:
    """The fixture every assertion above is built on has nothing to complain about, so a failure
    anywhere here is about the check under test and not about the fixture."""
    assert gamesystem.check_draw(_system()) == ()


# --------------------------------------------------------------------------- nothing ranks


def test_nothing_in_this_module_ranks_an_option() -> None:
    """§61(5), asserted over the module's own public surface rather than about one function.

    A promise like this breaks by somebody adding a helper, not by somebody editing a function —
    which is `test_no_number_describes_the_person`'s argument, one object along. `choose` takes
    the way it is told; `pending_choices` returns declaration order; there is no `best`, `score`,
    `rank`, `prefer` or `recommend` anywhere.
    """
    forbidden = ("best", "score", "rank_option", "prefer", "recommend", "suggest", "optimal")
    for name in gamesystem.__all__:
        assert not any(word in name.lower() for word in forbidden), name
    source = inspect.getsource(gamesystem)
    for word in ("def best", "def score", "def prefer", "def recommend"):
        assert word not in source


def test_the_progression_beat_never_names_a_fork() -> None:
    """`_named_moves` drops a `CHOOSE`, because taking a fork moves no number and the beat's
    sentence is that a named quantity *moves*. Naming one there would tell the scene something
    moved when nothing did — §161.4's own defect through the other door."""
    system = _system()
    risen = gamesystem.rise(gamesystem.starting_sheet(system, "mira"), at="s2").sheet
    moves = gamesystem.legal_moves(risen)
    assert any(move.kind is gamesystem.AdvanceKind.CHOOSE for move in moves)
    # `_named_moves` returns `(name, column)` pairs since §184, so the beat's word and the
    # number a later check reads cannot come apart. This assertion is about the words.
    named = {item.name for item in extraction._named_moves(system, moves)}
    assert "Hand" not in named
    assert "Reading" in named, "the ordinary moves are still named"


# --------------------------------------------------------------------------- the beat


def test_the_interaction_beat_fires_in_the_opening_and_nowhere_else_without_a_fork() -> None:
    """A book with no fork gains exactly one interaction beat — the smallest thing that answers
    read 10's standalone-comprehension item, since a character who opens their own state teaches
    its labels and its numbers by using them."""
    fires = [
        ordinal
        for ordinal in range(1, 9)
        if genre.interaction_text(ordinal, 8, reads=True) is not None
    ]
    assert fires == [1]
    assert genre.interaction_text(1, 8, reads=True) == genre.INTERACTION_BEAT


def test_a_book_that_prints_no_line_is_never_asked_to_open_one() -> None:
    """`reads` is the same value the planner passes to the furniture ask, so the beat cannot ask
    somebody to read an interface the writer was never handed. It is every book that speaks no
    system voice, and it renders nothing at all."""
    assert genre.interaction_text(1, 8, reads=False) is None
    assert genre.with_interaction("A scene.", 1, 8, reads=False) == "A scene."


def test_a_fork_standing_open_names_itself_and_its_ways_on_the_cadence() -> None:
    """Deliberation recurs for as long as a fork stands open, on the schedule the progression
    beat already runs at — so how much of it a book carries is a fact its own world declares and
    not a number this module picked."""
    offer = ("Hand", ("Kiln", "Reed"))
    scheduled = sorted(genre.beat_ordinals(8))
    for ordinal in scheduled:
        text = genre.interaction_text(ordinal, 8, reads=True, offer=offer)
        assert text is not None and "Hand stands open here" in text
        assert "Kiln and Reed" in text
    for ordinal in set(range(1, 9)) - set(scheduled):
        assert genre.interaction_text(ordinal, 8, reads=True, offer=offer) is None


def test_the_offer_form_wins_at_the_opening_where_both_could_fire() -> None:
    """It names the fork and its ways, which teaches the interface by using more of it."""
    text = genre.interaction_text(1, 8, reads=True, offer=("Hand", ("Kiln", "Reed", "Slack")))
    assert text is not None
    assert text.startswith("Hand stands open here")
    assert "Kiln, Reed and Slack" in text


def test_the_interaction_beat_carries_no_machinery_word_and_no_pronoun() -> None:
    """§155.3's two constraints, both already paid for. The first draft of the progression beat
    said *"something he has been counting"*, which would have written a male protagonist into
    every scheduled scene of every book this house drafts."""
    for text in (genre.INTERACTION_BEAT, genre.OFFER_BEAT):
        lowered = text.lower()
        assert not [word for word in house.MACHINERY_WORDS if word in lowered]
        assert not [
            word for word in (" he ", " she ", " his ", " her ", " him ") if word in lowered
        ]


def test_the_beat_says_weighs_and_never_says_pick() -> None:
    """The operator asked to read the deliberation. A beat that told the scene to settle the fork
    would spend the fork on the scene that introduces it, and taking one is a separate act with
    its own record."""
    assert "weighs" in genre.OFFER_BEAT
    for word in ("choose", "chooses", "picks", "decides", "settles"):
        assert word not in genre.OFFER_BEAT.lower()


def test_the_beat_costs_no_prompt_demand_because_it_is_not_prompt_text() -> None:
    """The reason this is a schedule and not a clause, with a number on it.

    `plan/house-genre-constraint.md` named the hazard — an instruction to make the system feel
    present is a §138 formula waiting to happen — and there is a second, arithmetic reason: the
    house floor and three of the roles standing on it sit exactly at their ceilings (§171.4), and
    a scene plan rides in the user prompt as book material rather than in the counted system
    message.
    """
    assert genre.INTERACTION_BEAT not in house.HOUSE_RULES
    assert genre.OFFER_BEAT not in house.HOUSE_RULES


# --------------------------------------------------------------------------- the reader


def test_the_offer_is_read_off_canon_and_abstains_where_the_book_cannot_answer() -> None:
    """`offered_choice` inherits every guard `movable_names` already applies, because the two
    answer one question about one book and a second set of rules would be a second answer."""
    system = _system()
    risen = gamesystem.rise(gamesystem.starting_sheet(system, "mira"), at="s2").sheet
    canon = [
        _accepted(record)
        for record in (
            *gamesystem.records_for(system),
            *gamesystem.records_for_sheet(risen, at="s2"),
        )
    ]
    assert extraction.offered_choice(canon, character="mira", at="s3") == (
        "Hand",
        ("Kiln", "Reed"),
    )
    assert extraction.offered_choice(canon, character=None, at="s3") is None
    assert extraction.offered_choice(canon, character="nobody", at="s3") is None
    assert extraction.offered_choice([], character="mira", at="s3") is None


def test_an_unreached_fork_is_not_offered_to_the_scene_that_precedes_it() -> None:
    """The plan cannot name a branch the book has not arrived at, which is the §167 discipline
    applied to a fork: reached-ness decides, and reaching is read off the sheet's own rung."""
    system = _system()
    opening = gamesystem.starting_sheet(system, "mira")
    canon = [
        _accepted(record)
        for record in (*gamesystem.records_for(system), *gamesystem.records_for_sheet(opening))
    ]
    assert extraction.offered_choice(canon, character="mira", at="s1") is None


def test_a_fork_named_in_this_system_s_own_vocabulary_abstains_whole() -> None:
    """`counted_names` drops one offending label because its list is a rotation and a short
    rotation still works. A fork named with one of its ways missing is a menu that lies about what
    is on offer, so the whole thing abstains and the beat falls back to the reading form."""
    system = _system(
        choices=(
            gamesystem.Choice(
                "fork_hand",
                "Hand",
                options=(
                    gamesystem.Option("opt_kiln", "Standing", grants=("cap_kiln",)),
                    gamesystem.Option("opt_reed", "Reed", grants=("cap_reed",)),
                ),
                opens_at="r_second",
            ),
        )
    )
    assert "standing" in house.MACHINERY_WORDS
    risen = gamesystem.rise(gamesystem.starting_sheet(system, "mira"), at="s2").sheet
    canon = [
        _accepted(record)
        for record in (
            *gamesystem.records_for(system),
            *gamesystem.records_for_sheet(risen, at="s2"),
        )
    ]
    assert extraction.offered_choice(canon, character="mira", at="s3") is None
