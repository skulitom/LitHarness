"""Which slot a world record goes in: what the tool documents, and what the readers read.

**Two defects, both found in pilots and neither of them a bug in any single function.** Every
function in `domain/worlds.py` reads the slot it always meant to read; what was wrong was the
prose in `world vocabulary` telling an Architect a different one, and the silence of
`world declare` about which slot it had just filled.

- `consequence` documented `--object` as carrying the rule while `consequence_domains` has
  always read it as the domain of life. Serial Pilot 13's first seed believed the
  documentation and left six records that no counter reads and no later declaration can
  replace — the slot a record fills is `(subject, predicate, object, order key)`, so a
  correction with a different edge is a different slot and `world accept` carries both.
- A `precedes` edge scoped by `--order-key` and carrying no `--value` belongs to every ladder
  at once, because `rank_order` reads a chain's criterion out of the value slot and ignores
  story position. Three sightings — Serial Pilot 7 §3.1.3, Serial Pilot 12 seed 1, Serial
  Pilot 13 seed 1, the last of which walked into it holding its own note about it.

So this file grades two things. The first is that every line of documented vocabulary is true
of the function that reads it, asserted by filling the slots the line names and checking the
reader finds them — a documentation test that fails when the documentation is wrong, which the
old prose could not do. The second is that `slot_warnings` says so at declare time and
**refuses nothing**: a world whose only fault is an unscoped `precedes` still validates clean
and still accepts, because transient incoherence is the Architect's working state by design
and `world accept` is the gate (§139.3).

No model call and no network; the end-to-end case drives `main(argv)` on a temporary store.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence

import litharness_contracts as lc
import pytest

from litharness.application import world as world_view
from litharness.cli import EXIT_OK, main
from litharness.domain import extraction, worlds
from tests.conftest import FIXTURE_SHEET


def rec(subject: str, predicate: str, **kwargs: object) -> lc.StateRecord:
    return worlds.world_record(subject, predicate, **kwargs)  # type: ignore[arg-type]


def accepted(record: lc.StateRecord) -> lc.StateRecord:
    """The same record as canon. Three readers below filter to canon and would see nothing."""
    return lc.StateRecord(
        record_id=record.record_id,
        kind=record.kind,
        subject=record.subject,
        predicate=record.predicate,
        value=record.value,
        object_ref=record.object_ref,
        story_position=record.story_position,
        authority=lc.StateAuthority.ACCEPTED_CANON,
        pov_visibility=list(record.pov_visibility),
        evidence=list(record.evidence),
        predicate_registry_version=record.predicate_registry_version,
        note=record.note,
    )


def sentences(records: Sequence[lc.StateRecord]) -> str:
    """Everything `project` renders, joined — for the predicates whose only reader is it."""
    return "\n".join(worlds.project(records).values())


# --- one probe per documented predicate ---------------------------------------------------
#
# Each probe fills the slots that predicate's line in `world vocabulary` names, asserts the
# function that reads that predicate comes back with what was put there, and returns the one
# record the line is about. The return is what lets the second test compare the prose to the
# record instead of to another piece of prose.

_RULE = rec("provenance", worlds.WORLD_RULE_PREDICATE, value="what a thing was fixes its price")
_CRITERION = [
    rec("crit_seal", worlds.TYPE_PREDICATE, value=worlds.CRITERION),
    rec("crit_seal", worlds.COMPARATOR_PREDICATE, value="ordinal"),
]
_LADDER = rec("first_seal", worlds.PRECEDES_PREDICATE, object_ref="second_seal", value="crit_seal")
_CLAIM = rec("q_who_pays", worlds.CLAIM_CONTENT, value="the assay house pays, and always has")


def _entity_role() -> lc.StateRecord:
    record = rec("saltmilk_doe", worlds.ENTITY_ROLE_PREDICATE, value="creature")
    assert worlds.entities_with_role([record], "creature") == ("saltmilk_doe",)
    return record


def _type() -> lc.StateRecord:
    record = rec("crit_seal", worlds.TYPE_PREDICATE, value=worlds.CRITERION)
    assert worlds.nodes_of_type([record], worlds.CRITERION) == ("crit_seal",)
    return record


def _world_rule() -> lc.StateRecord:
    assert worlds.rules([_RULE]) == ("provenance",)
    return _RULE


def _consequence() -> lc.StateRecord:
    """The rule is the subject and the domain is the edge. The line that said otherwise."""
    record = rec(
        "provenance",
        worlds.CONSEQUENCE_PREDICATE,
        object_ref="economy",
        value="a ledger is worth more than the vault it describes",
    )
    assert worlds.consequence_domains([_RULE, record]) == {"provenance": ("economy",)}
    return record


def _manifests_as() -> lc.StateRecord:
    record = rec("provenance", worlds.MANIFESTS_PREDICATE, value="a stamped receipt")
    assert worlds.manifestation_coverage([_RULE, record]).missing == ()
    return record


def _can_do() -> lc.StateRecord:
    """§160 put the holder's depth in the value slot, which was free; the edge still says who
    holds what, and a record written without a number reads exactly as it always did."""
    record = rec("kell", worlds.CAN_DO, object_ref="cap_read_grain", value=2)
    assert worlds.capabilities_of([record], "kell") == ("cap_read_grain",)
    assert "kell can do cap_read_grain at 2" in sentences([record])
    assert "kell can do cap_read_grain" in sentences(
        [rec("kell", worlds.CAN_DO, object_ref="cap_read_grain")]
    )
    return record


def _requires() -> lc.StateRecord:
    record = rec("cap_read_grain", worlds.REQUIRES, object_ref="cap_hold_a_glass", value=2)
    assert worlds.requirement_depth([record]) == 1
    assert "needs cap_hold_a_glass at 2 first" in sentences([record])
    return record


def _governed_by() -> lc.StateRecord:
    """The governed thing is the subject and the system is the edge — `RECOGNIZED_BY`'s
    direction, so an institution recognising a standing and a system granting one cannot
    invert against each other."""
    record = rec("crit_seal", worlds.GOVERNED_BY, object_ref="sys_the_weave")
    assert worlds.governed_by([record]) == {"crit_seal": "sys_the_weave"}
    assert worlds.governed([record], "sys_the_weave") == ("crit_seal",)
    return record


def _offers() -> lc.StateRecord:
    """The fork is the subject and the way is the edge, so a fork is found by its own edges —
    there is no `entity_role` for one, the way there is none for a criterion."""
    record = rec("fork_hand", worlds.OFFERS, object_ref="opt_kiln")
    assert worlds.offered_by([record], "fork_hand") == ("opt_kiln",)
    assert "fork_hand offers opt_kiln as one way to take it" in sentences([record])
    return record


def _grants() -> lc.StateRecord:
    """The way is the subject and the capability it opens is the edge. `gamesystem.SystemDef.gates`
    is what turns that into a lock: nothing may reach the capability until this way is taken."""
    record = rec("opt_kiln", worlds.GRANTS, object_ref="cap_kiln_hand")
    assert worlds.granted_by([record], "opt_kiln") == ("cap_kiln_hand",)
    assert "opt_kiln opens cap_kiln_hand to whoever takes it" in sentences([record])
    return record


def _chose() -> lc.StateRecord:
    """`stands_at`'s shape: the thing reached in the edge, the fork it was reached on in the
    value, and the position in the key — because a world may run several forks and an unscoped
    pick would splice two of them, which is `precedes`' own recorded reason."""
    record = rec("kell", worlds.CHOSE, object_ref="opt_kiln", value="fork_hand", order_key="0250")
    assert "kell took opt_kiln of fork_hand, and cannot take another" in sentences([record])
    return record


def _is_a() -> lc.StateRecord:
    """The name-bearing predicate, undocumented since Serial Pilot 1's operator-typed seed and
    now carrying the rung column's printed label."""
    record = rec("crit_seal", "is_a", value="the Third Seal")
    assert "seal" in worlds.key_nouns([record])
    return record


def _costs() -> lc.StateRecord:
    """The one documented predicate with no reader, and `COSTS` says why: every world already
    forged emits it for a rank, so giving it a sentence would change all their packets."""
    record = rec("cap_read_grain", worlds.COSTS, value="a day of your voice")
    assert worlds.project([record]) == {}
    # **The priced shape reads** (§210): a grant paid in a stock the rungs hand out fills
    # both slots, and that record alone has a sentence; the prose shape still has none.
    priced = rec("threadpull", worlds.COSTS, object_ref="marks", value=1)
    assert "threadpull is paid for in marks, 1 each time" in sentences([priced])
    return record


def _per_rung() -> lc.StateRecord:
    """§210: a grant every rung hands out. `gamesystem.systems_of` reads it onto the grant,
    and the packet says so in words."""
    record = rec("marks", worlds.PER_RUNG, value=2)
    assert "every rung hands out 2 marks" in sentences([record])
    return record


def _participant() -> lc.StateRecord:
    """§212: who a change happened to; `gamesystem.changes_of` reads it beside the effects."""
    record = rec("the_turn", worlds.PARTICIPANT_ROLE, object_ref="kell")
    anchor = rec("the_turn", worlds.TYPE_PREDICATE, value=worlds.CHANGE)
    assert "with kell" in sentences([anchor, record])
    return record


def _effect() -> lc.StateRecord:
    """§212: what a change did to a grant, the whole number it stands at afterwards; the
    packet says it, the game system reads it, and a value that is no number is warned about."""
    record = rec("the_turn", worlds.EFFECT_ROLE, object_ref="cap_read_grain", value=0)
    anchor = rec("the_turn", worlds.TYPE_PREDICATE, value=worlds.CHANGE)
    assert "results in cap_read_grain (0)" in sentences([anchor, record])
    assert worlds.slot_warnings(record) == ()
    wrong = rec("the_turn", worlds.EFFECT_ROLE, object_ref="cap_read_grain", value="gone")
    assert any("whole number" in warning for warning in worlds.slot_warnings(wrong))
    return record


def _taught_by() -> lc.StateRecord:
    record = rec("cap_read_grain", worlds.TAUGHT_BY, object_ref="mistress_ovin")
    assert "cap_read_grain is taught by mistress_ovin" in sentences([record])
    return record


def _comparator() -> lc.StateRecord:
    assert worlds.criteria(_CRITERION) == {"crit_seal": "ordinal"}
    return _CRITERION[1]


def _evaluates() -> lc.StateRecord:
    """The criterion is the subject and the thing judged is the edge — also written backwards."""
    record = rec("crit_seal", worlds.EVALUATES_PREDICATE, object_ref="assayer")
    assert "crit_seal is how assayer is judged" in sentences([*_CRITERION, record])
    return record


def _precedes() -> lc.StateRecord:
    assert worlds.ladder_of([*_CRITERION, _LADDER], "crit_seal") == ("first_seal", "second_seal")
    return _LADDER


def _stands_at() -> lc.StateRecord:
    record = rec(
        "kell",
        worlds.STANDS_AT_PREDICATE,
        object_ref="second_seal",
        value="crit_seal",
        order_key="s2",
    )
    canon = [accepted(item) for item in (*_CRITERION, _LADDER, record)]
    assert worlds.standing_of(canon, "kell") == {"crit_seal": "second_seal"}
    return record


def _asks() -> lc.StateRecord:
    record = rec("q_who_pays", worlds.QUESTION_PREDICATE, value="who pays for an assay")
    assert worlds.questions([record]) == {"q_who_pays": "who pays for an assay"}
    return record


def _reveal_scene() -> lc.StateRecord:
    record = rec("q_who_pays", worlds.REVEAL_SCENE, value=7)
    assert worlds.reveal_scenes([record]) == {"q_who_pays": 7}
    return record


def _claim_content() -> lc.StateRecord:
    assert worlds.claims([_CLAIM]) == {"q_who_pays": "the assay house pays, and always has"}
    return _CLAIM


def _claim_false() -> lc.StateRecord:
    """`--value true`, and only a literal true — `_scalar` is what turns the flag into one."""
    record = rec("q_who_pays", worlds.CLAIM_FALSE, value=True)
    assert worlds.false_claims([_CLAIM, record]) == frozenset({"q_who_pays"})
    return record


def _believes() -> lc.StateRecord:
    record = rec("kell", worlds.BELIEVES, object_ref="q_who_pays")
    assert "kell believes: the assay house pays" in sentences([_CLAIM, record])
    return record


def _disclosed_to() -> lc.StateRecord:
    """`--value reader` is what makes it a disclosure to the reader rather than to a person."""
    record = rec(
        "assay_house",
        worlds.DISCLOSED_TO,
        object_ref="q_who_pays",
        value=worlds.READER,
        order_key="s3",
    )
    assert worlds.disclosures([_CLAIM, record]) == {"q_who_pays": ("s3",)}
    return record


_PROTAGONIST = rec("kell", worlds.ENTITY_ROLE_PREDICATE, value="protagonist")
_EDGE = rec("kell", worlds.EDGE_PREDICATE, value="read a seal nobody stamped")
_PRICE = rec("kell", worlds.PRICE_PREDICATE, value="a day of their voice, each time")
_EXCEPTION = rec("kell", worlds.EXCEPTION_PREDICATE, object_ref="provenance")


def _brief() -> worlds.Protagonist:
    canon = [accepted(item) for item in (_PROTAGONIST, _EDGE, _PRICE, _EXCEPTION)]
    found = worlds.protagonist_brief(canon)
    assert found is not None
    return found


def _edge() -> lc.StateRecord:
    """Not an ordinary relationship, which is what the line said: it is the exception, in prose."""
    assert _brief().edge == "read a seal nobody stamped"
    return _EDGE


def _price() -> lc.StateRecord:
    assert _brief().price == "a day of their voice, each time"
    return _PRICE


def _exception_to() -> lc.StateRecord:
    assert _brief().exception == "provenance"
    return _EXCEPTION


# --- the three that were reachable and undocumented (§163) ---------------------------------
#
# All three are configuration in the value slot, so their readers live in `domain/extraction.py`
# rather than in `worlds.py`. That is why they were missed: every other line in this vocabulary
# documents a predicate `worlds.py` reads, and these are the ones a *different* module reads
# through the same `world declare`.

_SHEET_VALUE = {
    "fields": [
        {"name": "attunement", "label": "Attunement"},
        {"name": "threads", "label": "Threads", "paired": True},
    ]
}


def _status_sheet() -> lc.StateRecord:
    """The columns are the book's own, and `paired` is what mints the `_max` key."""
    record = rec("sera", extraction.SHEET_PREDICATE, value=_SHEET_VALUE)
    sheet = extraction.sheet_for([accepted(record)])
    assert sheet.value_keys == ("attunement", "threads", "threads_max")
    assert sheet != FIXTURE_SHEET
    return record


def _status_snapshot() -> lc.StateRecord:
    """Keyless is the entry state, and a zero-padded key is a schedule the scene does not read.

    **Both halves of the documented line, handed to the reader that acts on them** (§165). The
    line tells an Architect to leave the key off for the state the book opens in and to use
    zero-padded digits to schedule a later position; it now also promises that a scheduled
    snapshot is *not* folded into a scene. The second promise is the one Serial Pilot 15 needed
    and did not have, so the probe asserts it rather than only the first: the schedule is canon,
    `speaks_system_voice` sees it, and the line rendered at `s1` is still the opening state.

    The earlier version of this docstring said a keyless record "sorts below every minted `s{n}`",
    which was the exact belief that failed — a keyless record is not compared at all, it is
    carried through every position, and the thing that does sort below every `s{n}` is any
    numeric key an Architect writes.
    """
    record = rec(
        "sera",
        extraction.STATUS_PREDICATE,
        value={"attunement": 1, "threads": 2, "threads_max": 3},
    )
    sheet = rec("sera", extraction.SHEET_PREDICATE, value=_SHEET_VALUE)
    scheduled = rec(
        "sera",
        extraction.STATUS_PREDICATE,
        value={"attunement": 9, "threads": 3, "threads_max": 3},
        order_key="0350",
    )
    canon = [accepted(record), accepted(sheet), accepted(scheduled)]
    assert extraction.speaks_system_voice(canon)
    rendered = extraction.system_voice_example(canon, at="s1")
    assert rendered is not None
    assert "Attunement 1" in rendered and "Threads 2/3" in rendered
    assert "Attunement 9" not in rendered
    return record


def _graph_line() -> lc.StateRecord:
    record = rec(
        "sera",
        worlds.GRAPH_LINE_PREDICATE,
        value={"label": "ASSIZE", "edges": [{"predicate": "stands_at", "phrase": "now stands at"}]},
    )
    assert extraction.graph_line_fault([accepted(record)]) is None
    line = extraction.parse_graph_line(record.value)
    assert line.label == "ASSIZE"
    assert line.edges[0].predicate == "stands_at"
    return record


_PROBES: dict[str, Callable[[], lc.StateRecord]] = {
    "entity_role": _entity_role,
    "governed_by": _governed_by,
    "offers": _offers,
    "grants": _grants,
    "chose": _chose,
    "is_a": _is_a,
    "status_sheet": _status_sheet,
    "status_snapshot": _status_snapshot,
    "graph_line": _graph_line,
    "type": _type,
    "world_rule": _world_rule,
    "consequence": _consequence,
    "manifests_as": _manifests_as,
    "can_do": _can_do,
    "requires": _requires,
    "costs": _costs,
    "participant": _participant,
    "effect": _effect,
    "per_rung": _per_rung,
    "taught_by": _taught_by,
    "comparator": _comparator,
    "evaluates": _evaluates,
    "precedes": _precedes,
    "stands_at": _stands_at,
    "asks": _asks,
    "reveal_scene": _reveal_scene,
    "claim.content": _claim_content,
    "claim.false": _claim_false,
    "believes": _believes,
    "disclosed_to": _disclosed_to,
    "edge": _edge,
    "price": _price,
    "exception_to": _exception_to,
}


#: `costs` is documented as taking *either* slot and is therefore the one line the comparison
#: below cannot make, since a record fills one of them and the line names two. Named here
#: rather than skipped quietly: an exemption nobody can see is how a check comes to cover less
#: than it claims. Its shape is still asserted by its probe, which is what `COSTS` documents —
#: no reader at all beyond `state.describe`'s flat fallback.
_EITHER_SLOT = frozenset({worlds.COSTS})


@pytest.mark.parametrize("predicate", sorted(_PROBES))
def test_every_documented_slot_is_the_slot_its_reader_reads(predicate: str) -> None:
    """The whole documented vocabulary, one predicate at a time, against its own reader.

    Prose about a slot is unfalsifiable; a record built to that shape and handed to the
    function that reads it is not. What this pins is the *shape*: that a `consequence` with
    the domain in the edge is what `consequence_domains` counts, that a `precedes` with its
    criterion in the value is what `ladder_of` chains.
    """
    _PROBES[predicate]()


@pytest.mark.parametrize("predicate", sorted(set(_PROBES) - _EITHER_SLOT))
def test_the_documented_line_names_the_slots_its_own_record_fills(predicate: str) -> None:
    """And the prose is compared to that record rather than to another piece of prose.

    **This is the half that makes the pair falsifiable**, and without it the probes are only
    the author's reading of the documentation written down twice. The line must mention
    `--object` exactly when the verified record carries an edge and `--value` exactly when it
    carries one. Both defects this file is named for fail it: `consequence` named only
    `--object` for a record that needs both, and `edge` named `--object` for a record that
    has none.

    What it does **not** catch is a line that names the right slots and puts the wrong id in
    them — `evaluates` was backwards that way, and only its probe finds that. Stated because
    a check that is believed to cover more than it does is worse than one known to be narrow.
    """
    record = _PROBES[predicate]()
    line = world_view.vocabulary()["predicates"][predicate]
    assert ("--object" in line) == (record.object_ref is not None), line
    assert ("--value" in line) == (record.value is not None), line


def test_no_predicate_is_documented_without_a_probe() -> None:
    """The two sets are equal, so neither can grow alone.

    A predicate added to `world vocabulary` with no probe is a shape nothing verifies, and a
    probe with no documented line is a shape an Architect is never told about. Both are how
    the four wrong lines survived: nothing anywhere required the two to be the same set.
    """
    assert set(world_view.vocabulary()["predicates"]) == set(_PROBES)


# --- what `declare` says about a slot it cannot take back ----------------------------------


def test_the_rule_in_the_consequence_edge_is_named_as_the_mistake_it_is() -> None:
    """The pilot-13 record, and the warning names both the right slot and the permanence."""
    wrong = rec("provenance", worlds.CONSEQUENCE_PREDICATE, object_ref="provenance_rule")
    warning = " ".join(worlds.slot_warnings(wrong))
    assert "domain" in warning and "--value" in warning and "world accept" in warning


def test_a_consequence_in_its_documented_shape_is_warned_about_at_all() -> None:
    right = rec(
        "provenance",
        worlds.CONSEQUENCE_PREDICATE,
        object_ref="economy",
        value="a ledger outvalues the vault",
    )
    assert worlds.slot_warnings(right) == ()


def test_a_ladder_edge_scoped_by_story_time_is_flagged_at_the_moment_it_is_declared() -> None:
    """Three pilots walked into this and the third was carrying a note about it.

    The edge is legal, stores, and reads back — and joins every chain in the world, which is
    why nothing downstream could ever name it. Eleven `world check` complaints named the
    standings instead, and one seed read those and concluded the CLI was broken.
    """
    edge = rec("first_seal", worlds.PRECEDES_PREDICATE, object_ref="second_seal", order_key="s1")
    warning = " ".join(worlds.slot_warnings(edge))
    assert "--value" in warning and "--order-key" in warning


def test_an_edge_that_names_its_criterion_is_scoped_however_it_is_positioned() -> None:
    """`--value` is what scopes a chain, so an edge that carries one has nothing wrong with it."""
    edge = rec(
        "first_seal",
        worlds.PRECEDES_PREDICATE,
        object_ref="second_seal",
        value="crit_seal",
        order_key="s1",
    )
    assert worlds.slot_warnings(edge) == ()


def test_an_unpositioned_edge_with_no_criterion_is_the_common_world_and_not_a_mistake() -> None:
    """`rank_order`: an edge with no criterion belongs to every ladder, *which is right for the
    common world with one*. Flagging it would report a world that is correct."""
    edge = rec("first_seal", worlds.PRECEDES_PREDICATE, object_ref="second_seal")
    assert worlds.slot_warnings(edge) == ()


def test_a_flagged_declaration_is_still_a_coherent_world_by_the_validator() -> None:
    """Report-shaped and not a rule clause: `validate` gains nothing, so `accept` refuses nothing.

    The distinction is the whole design. `world accept` is the gate and it fires on
    contradiction; an edge in the wrong slot contradicts nothing, and a validator clause here
    would refuse the single-ladder worlds that are allowed to leave the value empty.
    """
    records = [
        rec("crit_seal", worlds.TYPE_PREDICATE, value=worlds.CRITERION),
        rec("crit_seal", worlds.COMPARATOR_PREDICATE, value="ordinal"),
        rec("first_seal", worlds.PRECEDES_PREDICATE, object_ref="second_seal", order_key="s1"),
    ]
    assert worlds.validate(records) == ()
    assert any(worlds.slot_warnings(record) for record in records)


def test_the_check_view_carries_the_warnings_without_moving_its_verdict() -> None:
    """Serial Pilot 12 read this view, saw only the downstream complaints, and misdiagnosed."""
    records = [
        rec("crit_seal", worlds.TYPE_PREDICATE, value=worlds.CRITERION),
        rec("crit_seal", worlds.COMPARATOR_PREDICATE, value="ordinal"),
        rec("first_seal", worlds.PRECEDES_PREDICATE, object_ref="second_seal", order_key="s1"),
    ]
    payload = world_view.check(records)
    assert payload["ok"] is True
    assert len(payload["will_not_resolve"]) == 1


# --- the same thing through the command an Architect actually runs -------------------------


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITHARNESS_FAKE_PAD_CHARS", "400")


def seeded(tmp_path) -> str:  # type: ignore[no-untyped-def]
    db = tmp_path / "world.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    assert (
        main(["--database", str(db), "listing", "--writer", "vance", "--scenes", "24"]) == EXIT_OK
    )
    return str(db)


def test_declare_separates_what_will_settle_from_what_never_will(fake, tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    """Both lists, on one record, in the JSON an agent parses.

    `not_yet_coherent` is a promise that the rest of the world settles this; that promise is
    kept for a question awaiting its answer and broken for a record in the wrong slot. Until
    these were two keys they read identically, which is how six dead records were declared
    under a heading that said "not yet".
    """
    db = seeded(tmp_path)
    capsys.readouterr()
    assert (
        main(
            [
                "--database",
                db,
                "world",
                "declare",
                "provenance",
                "consequence",
                "--object",
                "provenance",
                "--value",
                "a ledger outvalues its vault",
                "--json",
            ]
        )
        == EXIT_OK
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["will_not_resolve"], "the slot mistake was not reported at declare time"
    assert "--value" in payload["will_not_resolve"][0]


def test_a_ladder_edge_in_story_time_is_reported_and_still_accepted(fake, tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    """Reported at declare, and `accept` still takes it — report, never refuse.

    The Architect's transient incoherence is by design and `world accept` is the only gate, so
    a warning that blocked acceptance would be the rule clause this deliberately is not.
    """
    db = seeded(tmp_path)
    capsys.readouterr()
    assert (
        main(
            [
                "--database",
                db,
                "world",
                "declare",
                "first_seal",
                "precedes",
                "--object",
                "second_seal",
                "--order-key",
                "s1",
            ]
        )
        == EXIT_OK
    )
    printed = capsys.readouterr()
    assert "will not resolve" in printed.err
    assert "--value" in printed.err
    assert main(["--database", db, "world", "accept"]) == EXIT_OK
    assert "accepted 1" in capsys.readouterr().out


def test_a_records_identity_is_blind_to_its_order_key() -> None:
    """The fifth wrong line in this vocabulary, and it was wrong in the reassuring direction.

    `how` told the Architect that a corrected declaration changing the subject, the `--object`
    **or the `--order-key`** fills a different slot so both survive. The first two are true.
    The third is not: `record_id_for` keys on `(subject, predicate, object_ref, value)` and
    carries no position, so a redeclaration that moves only the position is the same record.
    """
    at_one = rec("kell", worlds.STANDS_AT_PREDICATE, object_ref="a", value="c", order_key="s1")
    at_seven = rec("kell", worlds.STANDS_AT_PREDICATE, object_ref="a", value="c", order_key="s7")
    assert at_one.record_id == at_seven.record_id, "position is not part of identity"
    moved = rec("kell", worlds.STANDS_AT_PREDICATE, object_ref="b", value="c", order_key="s1")
    assert at_one.record_id != moved.record_id, "the edge is part of identity"


def test_repositioning_a_declared_fact_does_not_land_and_says_so(fake, tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    """And the store keeps the FIRST position, which is why the old line was dangerous.

    `record_state_records` is INSERT OR IGNORE on that id, so the second declaration is
    dropped. It is not silent — `declare` answers `already on record` — but an Architect told
    it had just filled a second slot would read that as confirmation while the wrong position
    stood.
    """
    db = seeded(tmp_path)
    capsys.readouterr()
    for key in ("s1", "s7"):
        assert (
            main(
                [
                    "--database",
                    db,
                    "world",
                    "declare",
                    "kell",
                    "stands_at",
                    "--object",
                    "second_seal",
                    "--value",
                    "crit_seal",
                    "--order-key",
                    key,
                ]
            )
            == EXIT_OK
        )
    printed = capsys.readouterr().out
    assert "already on record" in printed

    capsys.readouterr()
    assert main(["--database", db, "world", "show", "--subject", "kell", "--json"]) == EXIT_OK
    rows = json.loads(capsys.readouterr().out)
    standings = [row for row in rows if row["predicate"] == "stands_at"]
    assert len(standings) == 1, "the reposition became a second record after all"
    assert standings[0]["order_key"] == "s1", "the second declaration moved the first"


def test_a_world_with_no_sheet_is_told_so_and_is_still_a_coherent_world() -> None:
    """The gap is the third list and it moves no verdict (§163).

    A half-built world has no sheet yet and that is the ordinary state, so this reports and
    `ok` stays what `validate` says. The floor refuses at draft time, where the answer is
    final; refusing here would refuse every world in the middle of being built.
    """
    payload = world_view.check([_RULE])
    assert payload["ok"] is True
    assert payload["complaints"] == []
    assert any("status_snapshot" in gap for gap in payload["gaps"])


def test_the_missing_system_is_a_separate_gap_from_the_missing_sheet() -> None:
    """Two questions, both reported, because a world can fail either without the other.

    The floor asks whether this book can speak system voice at all; §160's `system_gap` asks
    whether the sheet it speaks with belongs to a system the world declared. A hand-seeded
    sheet answers the first and not the second, which is every book on disk today.
    """
    hand_seeded = [accepted(_status_snapshot()), accepted(_status_sheet())]
    payload = world_view.check(hand_seeded)
    assert payload["ok"] is True
    assert not any("status_snapshot" in gap for gap in payload["gaps"]), "the floor is clear"
    assert any("no game system" in gap for gap in payload["gaps"]), payload["gaps"]


def test_the_gap_closes_on_exactly_what_the_genre_floor_reads() -> None:
    """One question, asked through `genre.has_starting_sheet` rather than restated.

    A canon snapshot with a prose value does **not** close it, which is §158's whole
    correction: the sheet the writer is shown is rendered out of a mapping, so a predicate
    that answered yes to prose would let a book pass and never be asked for a line.
    """
    prose = accepted(rec("sera", extraction.STATUS_PREDICATE, value="attuned, two threads"))

    def floor_gaps(records: list[lc.StateRecord]) -> list[str]:
        """Only the floor's own gap. The system gap is a separate question and stays open on
        a hand-seeded book, which is every book on disk today."""
        return [gap for gap in world_view.check(records)["gaps"] if "status_snapshot" in gap]

    assert floor_gaps([prose]), "a prose sheet is not a sheet the line renders"
    assert floor_gaps([prose, accepted(_status_snapshot())]) == []


def test_a_proposed_sheet_leaves_the_gap_open_because_accept_is_the_gate() -> None:
    """The Architect declaring one is not the book having one; `world accept` is the act."""
    assert world_view.check([_status_snapshot()])["gaps"], "a proposal is not canon"


def test_the_predicates_the_vocabulary_names_are_the_ones_that_clear_the_floor(
    fake, tmp_path, capsys
) -> None:  # type: ignore[no-untyped-def]
    """The handshake, end to end on the commands an Architect actually holds (§163).

    Both predicates were reachable and neither was written down, in the command
    `world_agent`'s prompt calls the list of every predicate the world's language admits. This
    drives the documented shapes through the real CLI and asserts the book ends up rendering
    **its own** columns — the counterfactual that makes the omission a finding rather than a
    theory, since a book that declares no sheet is not sheetless but on the retired default sheet.
    """
    db = seeded(tmp_path)
    capsys.readouterr()
    for argv in (
        ["world", "declare", "sera", "status_sheet", "--value", json.dumps(_SHEET_VALUE)],
        [
            "world",
            "declare",
            "sera",
            "status_snapshot",
            "--value",
            json.dumps({"attunement": 1, "threads": 2, "threads_max": 3}),
        ],
    ):
        assert main(["--database", db, *argv]) == EXIT_OK

    def floor_gap_open() -> bool:
        capsys.readouterr()
        assert main(["--database", db, "world", "check", "--json"]) == EXIT_OK
        gaps = json.loads(capsys.readouterr().out)["gaps"]
        return any("status_snapshot" in gap for gap in gaps)

    assert floor_gap_open(), "not canon until accept"
    assert main(["--database", db, "world", "accept"]) == EXIT_OK
    assert not floor_gap_open(), "the documented predicates did not clear the floor"


def test_the_vocabulary_an_architect_reads_names_the_domain_and_the_criterion(
    fake, tmp_path, capsys
) -> None:  # type: ignore[no-untyped-def]
    """The end of the loop: the command whose answer was wrong now answers with the slot.

    `world vocabulary` is the only place the shapes are written down — `world_agent`'s prompt
    sends the Architect here rather than carrying a copy — so this is the whole of what a
    fresh draw is told.
    """
    db = seeded(tmp_path)
    capsys.readouterr()
    assert main(["--database", db, "world", "vocabulary"]) == EXIT_OK
    predicates = json.loads(capsys.readouterr().out)["predicates"]
    assert "consequence_domains" in predicates["consequence"]
    assert "--value the criterion" in predicates["precedes"]
    assert "comparator" in predicates
