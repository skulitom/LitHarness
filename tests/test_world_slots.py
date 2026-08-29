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
from litharness.domain import worlds


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
_LADDER = rec(
    "first_seal", worlds.PRECEDES_PREDICATE, object_ref="second_seal", value="crit_seal"
)
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
    record = rec("kell", worlds.CAN_DO, object_ref="cap_read_grain")
    assert worlds.capabilities_of([record], "kell") == ("cap_read_grain",)
    return record


def _requires() -> lc.StateRecord:
    record = rec("cap_read_grain", worlds.REQUIRES, object_ref="cap_hold_a_glass")
    assert worlds.requirement_depth([record]) == 1
    return record


def _costs() -> lc.StateRecord:
    """The one documented predicate with no reader, and `COSTS` says why: every world already
    forged emits it for a rank, so giving it a sentence would change all their packets."""
    record = rec("cap_read_grain", worlds.COSTS, value="a day of your voice")
    assert worlds.project([record]) == {}
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


_PROBES: dict[str, Callable[[], lc.StateRecord]] = {
    "entity_role": _entity_role,
    "type": _type,
    "world_rule": _world_rule,
    "consequence": _consequence,
    "manifests_as": _manifests_as,
    "can_do": _can_do,
    "requires": _requires,
    "costs": _costs,
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
