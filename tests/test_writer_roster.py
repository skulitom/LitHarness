"""The roster as records: what a machine may write, and what only a decision may.

Stage-0 §146's recruiter brief. The roster was four dossiers compiled into
`domain/writers.py` and nothing could grow it. Making it a table opens exactly one new way for
this project to go wrong — a machine that proposes a writer could end up casting one — so the
tests below are mostly about the gap between `proposed` and `accepted` and about the things that
must stay true across it.

Four properties are load-bearing and every one of them fails silently, by storing a row,
resolving a name, or returning a writer, none of which raises:

1. **A proposal is not castable.** `--writer <name>` must refuse a declared-but-not-accepted
   writer, because a recruit that could draft merely by being named makes acceptance optional.
2. **A stored row can never shadow a compiled one.** The four in `CAST` are the controls the
   roster is read against; a store row answering to one of their names would not fail, it
   would quietly answer.
3. **A row round-trips to a `Writer` that still addresses itself.** Interests are addressed
   material and their order is part of the address, so a storage format that loses order stores
   rows no `Writer` can be rebuilt from.
4. **An `accepted` row cannot exist without a decision row to point at.** That property was
   carried by nothing but who happened to hold the pen in three earlier subsystems.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.cli import _resolve_writer
from litharness.domain import writers
from litharness.domain.policy import (
    GateKind,
    GateOutcome,
    Outcome,
    PolicyDecision,
    decision_id_for,
)

DOSSIER = (
    "You write the kind of fantasy where the stakes are a bakery, a bad harvest and "
    "somebody's estranged aunt. What you love is competence at low volume. You want a "
    "reader to close a chapter feeling like they could stay."
)


@pytest.fixture
def store(tmp_path):
    with SqliteStore.open(tmp_path / "roster.db") as opened:
        yield opened


def _propose(store: SqliteStore, name: str = "okafor", **kwargs) -> writers.Writer:
    writer = writers.build(
        name,
        kwargs.pop("dossier", DOSSIER),
        interests=kwargs.pop("interests", ("cozy fantasy", "small towns")),
        note=kwargs.pop("note", ""),
    )
    store.record_proposed_writer(
        writer,
        specialization=kwargs.pop("specialization", "cozy-fantasy"),
        shape=kwargs.pop("shape", "several-no-beat"),
        proposed_at=kwargs.pop("proposed_at", "2026-08-28T00:00:00Z"),
    )
    return writer


def _accept(store: SqliteStore, *writer_ids: str, at: str = "2026-08-28T01:00:00Z") -> int:
    gate = GateOutcome(
        gate=GateKind.SHAPE,
        rule_or_critic_id="roster.accept.v0",
        passed=True,
        blocking=False,
        detail="test",
    )
    return store.accept_writers(
        writer_ids,
        decision=PolicyDecision(
            decision_id=decision_id_for("roster-accept:" + "+".join(writer_ids), 0, (gate,)),
            outcome=Outcome.ACCEPT,
            gates=(gate,),
            reason="a person put these writers on the roster",
        ),
        accepted_at=at,
    )


# ------------------------------------------------------------------ proposal and admission


def test_a_recruit_lands_proposed_and_no_row_can_claim_acceptance_without_a_decision(
    store,
) -> None:
    """Rail 4, held by the schema rather than by a caller's manners.

    `record_proposed_writer` has no parameter that could write `accepted`, and the CHECK in
    migration 035 makes a row that claims it without a `decision_id` unrepresentable — which is
    the laundering path (`027_directive_author.sql`) closed before a machine reaches this table.
    """
    writer = _propose(store)
    (row,) = store.roster_rows()
    assert row["status"] == writers.RosterStatus.PROPOSED.value
    assert row["accepted_at"] is None and row["decision_id"] is None

    with pytest.raises(sqlite3.IntegrityError):
        store._connection.execute(
            "UPDATE roster_writers SET status = 'accepted' WHERE writer_id = ?",
            (writer.writer_id,),
        )


def test_accepting_moves_the_row_and_points_it_at_the_decision_that_carried_it(store) -> None:
    writer = _propose(store)
    assert _accept(store, writer.writer_id) == 1
    (row,) = store.roster_rows()
    assert row["status"] == writers.RosterStatus.ACCEPTED.value
    assert row["accepted_at"] and row["decision_id"]
    assert store.load_decision(row["decision_id"]).outcome is Outcome.ACCEPT


def test_a_proposed_writer_is_not_castable_and_the_refusal_names_the_act_that_would_cast_it(
    store,
) -> None:
    """The gap between the two statuses is a person, and this is the sentence that says so."""
    _propose(store)
    writer, reason = _resolve_writer("okafor", store)
    assert writer is None
    assert "proposed but not accepted" in reason
    assert "roster accept okafor" in reason


def test_an_accepted_writer_resolves_and_carries_its_dossier_into_a_prompt(store) -> None:
    proposed = _propose(store)
    _accept(store, proposed.writer_id)
    writer, reason = _resolve_writer("okafor", store)
    assert reason == ""
    assert writer is not None
    assert writer.writer_id == proposed.writer_id
    assert "estranged aunt" in writer.render()


def test_accepting_a_writer_twice_is_idempotent_rather_than_a_second_admission(store) -> None:
    writer = _propose(store)
    assert _accept(store, writer.writer_id) == 1
    # The UPDATE is scoped `WHERE status = 'proposed'`, so a replay moves nothing rather than
    # re-stamping an accepted row with a second decision.
    assert _accept(store, writer.writer_id) == 0


# --------------------------------------------------------------------------- the namespace


def test_the_store_refuses_a_recruit_who_takes_a_compiled_cast_name(store) -> None:
    """A stored row wearing a control's name would not fail; it would quietly answer."""
    for reserved in ("ferreira", "halloran", "geology", "volcanology"):
        with pytest.raises(writers.IllegalDossier):
            _propose(store, reserved)
    assert store.roster_rows() == []


def test_a_stored_row_can_never_shadow_a_cast_writer(store) -> None:
    """The second lock, for the case the write-time guard cannot see: `CAST` growing *later*
    to a name a stored writer already holds. Where it fires nothing resolves, and neither
    writer is silently preferred."""
    writer = _propose(store, "smuggled")
    _accept(store, writer.writer_id)
    store._connection.execute(
        "UPDATE roster_writers SET name = 'ferreira' WHERE writer_id = ?",
        (writer.writer_id,),
    )
    resolved, reason = _resolve_writer("ferreira", store)
    assert resolved is None
    assert "names both a stored writer and a compiled one" in reason


def test_only_one_accepted_writer_can_answer_to_a_name(store) -> None:
    """`--writer <name>` has to have one answer, and the partial index is what guarantees it.

    The refusal is raised with both ids rather than left to `sqlite3.IntegrityError`, because
    nothing in the adapter package translates that into a sentence an operator can act on.
    """
    first = _propose(store)
    _accept(store, first.writer_id)
    second = _propose(store, dossier=DOSSIER.replace("bakery", "brewery"))
    assert first.writer_id != second.writer_id
    with pytest.raises(writers.IllegalDossier) as caught:
        _accept(store, second.writer_id)
    assert first.writer_id in str(caught.value)
    assert second.writer_id in str(caught.value)


def test_two_recruits_may_be_proposed_under_one_name_because_a_proposal_is_not_an_admission(
    store,
) -> None:
    """A plain `UNIQUE (name)` would fail at the agent's drafting point rather than the
    operator's decision point, and content-addressing says an edited dossier is a *different*
    writer that has to be able to coexist with the one that already wrote books."""
    _propose(store)
    _propose(store, dossier=DOSSIER.replace("bakery", "brewery"))
    assert len({row["writer_id"] for row in store.roster_rows(name="okafor")}) == 2


# ------------------------------------------------------------------------- the round trip


def test_the_interest_order_survives_storage_so_the_row_still_addresses_itself(store) -> None:
    """Order is addressed material: `writer_id_for` length-prefixes the interest field
    precisely so `("a", "b")` and `("a\\x1fb",)` cannot address to the same writer. A store that
    sorted, de-duplicated or joined would keep rows no `Writer` can be rebuilt from, and
    `accepted_writer` would raise on every read instead of returning a drafter."""
    writer = _propose(store, interests=("b", "a", "c"))
    _accept(store, writer.writer_id)
    (row,) = store.roster_rows()
    assert row["interests"] == ("b", "a", "c")
    rebuilt = store.accepted_writer("okafor")
    assert rebuilt is not None and rebuilt.writer_id == writer.writer_id


def test_editing_an_addressed_column_in_place_makes_the_row_refuse_to_load(store) -> None:
    """The whole reason for a content address: a roster cannot drift under the books it wrote.

    The stored id is passed to the constructor rather than recomputed, so the address check
    stays live — recomputing here would make every row address itself by construction.
    """
    writer = _propose(store)
    _accept(store, writer.writer_id)
    store._connection.execute(
        "UPDATE roster_writers SET dossier = ? WHERE writer_id = ?",
        (DOSSIER.replace("bakery", "brewery"), writer.writer_id),
    )
    with pytest.raises(writers.IllegalDossier):
        store.accepted_writer("okafor")


def test_the_note_and_the_shelf_are_outside_the_address_so_a_second_proposal_is_the_same_row(
    store,
) -> None:
    """They say why this writer was drafted, not who they are. Two recruits for different
    shelves whose dossiers came out identical are one writer and one row, and the insert is
    idempotent on the address rather than a silent rewrite."""
    first = _propose(store, note="one", specialization="cozy-fantasy")
    second = _propose(store, note="two", specialization="light-fantasy")
    assert first.writer_id == second.writer_id
    (row,) = store.roster_rows()
    assert row["specialization"] == "cozy-fantasy"


def test_a_shape_outside_the_registered_vocabulary_is_refused_at_write_time(store) -> None:
    """An unlabelled recruit drops out of the registered arm without saying so."""
    with pytest.raises(writers.IllegalDossier):
        _propose(store, shape="whatever")
    assert store.roster_rows() == []


def test_a_malformed_interests_column_is_an_integrity_failure_rather_than_a_silent_tuple(
    store,
) -> None:
    from litharness.adapters.sqlite_errors import IntegrityFailure

    writer = _propose(store)
    store._connection.execute(
        "UPDATE roster_writers SET interests_json = ? WHERE writer_id = ?",
        (json.dumps({"not": "a list"}), writer.writer_id),
    )
    with pytest.raises(IntegrityFailure):
        store.roster_rows()


# ---------------------------------------------------------------------------- resolution


def test_the_compiled_cast_still_resolves_without_a_store_at_all(store) -> None:
    """`prompts` has never touched a database and must not start creating one."""
    writer, reason = _resolve_writer("ferreira", None)
    assert reason == "" and writer is writers.CAST["ferreira"]


def test_an_unknown_name_is_refused_loudly_rather_than_defaulted_to_nobody(store) -> None:
    """`_director_id`'s rule: a typo that silently produced the control arm is the worst
    failure available to a run whose whole question is whether the arms differ."""
    writer, reason = _resolve_writer("nobody", store)
    assert writer is None
    assert "the cast is" in reason
    assert "roster show" in reason


def test_an_empty_name_is_the_anonymous_control_and_is_not_an_error(store) -> None:
    assert _resolve_writer("", store) == (None, "")


def test_a_probe_writer_is_reserved_but_never_resolvable(store) -> None:
    """The ten in `BUILTIN` measure whether a dossier binds at all. Not one reads the genre
    this project publishes in and none has ever reached a prompt, so `--writer geology` drafting
    a book would be a behaviour change nobody asked for. The name stays reserved all the same."""
    assert "geology" in writers.RESERVED_NAMES
    writer, reason = _resolve_writer("geology", store)
    assert writer is None and "the cast is" in reason
