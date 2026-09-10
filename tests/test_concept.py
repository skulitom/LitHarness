"""Concept persistence and the separate listing, world and planning inputs. No model calls."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import concept, discovery, export, outline, overview, world_agent
from litharness.cli import EXIT_FAULT, EXIT_OK, main
from litharness.domain import house
from litharness.domain import writers as writers_domain
from litharness.domain.beats import arc_template, beats_for
from litharness.domain.generation import CompletionResult, Usage
from litharness.domain.plans import constraints_of, premise_of
from litharness.domain.revision import new_book

WRITER = writers_domain.CAST["ferreira"]


def _example() -> dict[str, object]:
    """The operator's example premise, in the schema's fields.

    A system-apocalypse Earth, a botched portal spell survived on stats for years, emergence on
    the far side of the universe under a competing system, some old abilities kept. Recorded in
    `plan/serial-pilot-21.md` §5 as the shape the pipeline could not invent or print; this is the
    check that the schema can now at least hold it.
    """
    return {
        "person_before": "a second-year physics dropout stacking shelves on nights",
        "exception": "the only person the portal spell failed to kill, because his stats held",
        "first_use": "he walks out of a spell that has killed everyone else who touched it",
        "want": "to stop being the one thing in any room that does not belong there",
        "system": {
            "name": "the Tally",
            "manner": "in a clerk's voice that counts out loud and apologises for nothing",
            "look": "grey ledger lines on the inside of the eye, lit from behind",
            "steps": 12,
            "strongest_known": "the seventh step, held by three people on Earth",
            "pays": "a step up is a night you do not have to run from anything",
        },
        "threat": {
            "what": "the things that came through with the Tally and eat what cannot outrun them",
            "first_reach": "the market on the far side, the first night he is out of the portal",
        },
        "turn": {
            "event": (
                "the portal collapses on him and holds for eleven years; he walks out on the "
                "far side of the universe with the Tally gone silent"
            ),
            "when": "before chapter one",
        },
        "second_system": {
            "name": "the Accord",
            "manner": "as a voice that bargains, in a language he only half has",
            "kept": "his Tally endurance and his reading of a thing's next move",
        },
        "first_arc": {
            "opens": "he walks out of the portal into a market that has never seen his kind",
            "middle": "the Accord offers him a step it has never offered an outsider",
            "closes": "he takes it and learns what the Tally was to the Accord",
        },
        "debts": [
            {
                "subject": "the silence of the Tally",
                "owed": "why the first system went quiet on the far side",
                "due_scene": 5,
            },
            {
                "subject": "the eleven years",
                "owed": "what the portal did with the time",
                "due_scene": 6,
            },
        ],
    }


# --- the schema holds the operator's example, and refuses what the stages cannot use ---------


def test_the_schema_holds_the_operator_s_example_premise_and_it_round_trips() -> None:
    drawn = concept.Concept.from_payload(_example())
    assert drawn.second_system is not None
    assert drawn.second_system.kept.startswith("his Tally endurance")
    assert drawn.turn.when == concept.BEFORE_CHAPTER_ONE
    assert drawn.system.steps == 12
    again = concept.Concept.from_text(drawn.to_text())
    assert again == drawn
    assert json.loads(drawn.to_text()) == drawn.to_jsonable()


def test_the_schema_has_no_slot_for_an_opinion() -> None:
    """The listing loop's containment, one stage up: no verdict field, no score, no ranking."""
    properties = concept.CONCEPT_SCHEMA["properties"]
    assert set(properties) == {
        "person_before",
        "exception",
        "first_use",
        "want",
        "system",
        "threat",
        "turn",
        "second_system",
        "first_arc",
        "debts",
    }
    assert set(properties) == set(concept.CONCEPT_SCHEMA["required"])


@pytest.mark.parametrize(
    ("break_it", "named"),
    [
        (lambda p: p.__setitem__("debts", p["debts"][:1]), "debts"),
        (lambda p: p["turn"].__setitem__("when", "whenever"), "turn.when"),
        (lambda p: p["system"].__setitem__("steps", 1), "system.steps"),
        (lambda p: p.__setitem__("second_system", "the Accord"), "second_system"),
        (lambda p: p["first_arc"].__setitem__("closes", ""), "first_arc.closes"),
    ],
)
def test_a_concept_the_stages_cannot_use_is_refused_with_the_field_named(
    break_it: object, named: str
) -> None:
    payload = _example()
    break_it(payload)  # type: ignore[operator]
    with pytest.raises(concept.MalformedConcept) as refusal:
        concept.Concept.from_payload(payload)
    assert named in str(refusal.value)


def test_a_one_system_concept_is_legal_and_says_so() -> None:
    payload = _example()
    payload["second_system"] = None
    drawn = concept.Concept.from_payload(payload)
    assert drawn.second_system is None
    assert "second system" not in drawn.render()


# --- the request ---------------------------------------------------------------------------


def test_the_request_carries_the_writer_the_brief_the_person_the_arc_length_and_the_shelf() -> None:
    request = concept.render_concept_request(
        "a portal accident that costs years",
        WRITER,
        scenes=6,
        person="first",
        blurbs="How this shelf's listings sound:\n\nA blurb.",
    )
    assert (request.system or "").startswith(WRITER.render())
    assert "a portal accident that costs years" in request.prompt
    assert overview.FIRST_PERSON_ASK in request.prompt
    assert "The first arc is 6 scenes." in request.prompt
    assert request.prompt.startswith("How this shelf's listings sound:")
    assert request.schema is concept.CONCEPT_SCHEMA
    assert request.profile == concept.CONCEPT_PROFILE
    assert request.call_class == "generation"


def test_the_task_text_speaks_none_of_this_system_s_own_vocabulary() -> None:
    """The listing writer reads the rendered concept, so a machinery word here is one remove
    from a reader. `tests/test_prompt_budget.py` holds the same rail over the assembled role."""
    text = concept.render_concept_request("", WRITER, scenes=6).system or ""
    found = sorted(word for word in house.MACHINERY_WORDS if word in text.lower())
    assert not found, found


@pytest.mark.parametrize(
    "brief",
    ["", "A native-born gardener explores her own world. No portals or apocalypse."],
)
def test_new_invention_defaults_to_the_requested_genres_under_the_author_brief(brief: str) -> None:
    for request in (
        discovery.render_request(brief),
        concept.render_concept_request(brief, scenes=6),
    ):
        assert "portal fantasy, isekai, or system apocalypse" in request.system
        assert "or a combination" in request.system
        assert "unless the author's brief calls for something else" in request.system
        if brief:
            assert brief in request.prompt
    assert discovery.Discovery.from_invention(_discovery()).version == "magical-discovery.v5"


# --- where it lives ------------------------------------------------------------------------


def test_the_concept_is_a_book_plan_item_and_never_an_author_lock() -> None:
    drawn = concept.Concept.from_payload(_example())
    item = drawn.plan_item()
    assert item.kind is lc.PlanKind.BOOK_PLAN
    assert item.logical_id == concept.CONCEPT_PLAN_ID
    assert not item.locked
    premise = lc.PlanItem(
        logical_id="plan-premise",
        kind=lc.PlanKind.PREMISE,
        text="A premise.",
        authority=lc.PlanAuthority.INTENDED,
        locked=True,
    )
    # The scene call's locked block carries constraints and promises; the concept is neither.
    assert constraints_of([premise, item]) == ()
    assert premise_of([premise, item]) == "A premise."
    assert concept.concept_of([premise, item]) == drawn
    assert concept.concept_of([premise]) is None


def test_a_concept_the_book_carries_but_cannot_read_is_a_fault_and_not_an_absence() -> None:
    broken = lc.PlanItem(
        logical_id=concept.CONCEPT_PLAN_ID,
        kind=lc.PlanKind.BOOK_PLAN,
        text="not json",
        authority=lc.PlanAuthority.INTENDED,
    )
    with pytest.raises(concept.MalformedConcept):
        concept.concept_of([broken])


# --- what each stage is told, and byte-identity without it ---------------------------------


def test_the_listing_is_written_from_the_concept_and_renders_as_it_was_without_one() -> None:
    drawn = concept.Concept.from_payload(_example())
    with_it = overview.render_overview_request(
        "a brief", WRITER, person="first", concept=drawn.render_for_listing()
    )
    without = overview.render_overview_request("a brief", WRITER, person="first")
    assert "The book this listing sells, as its writer conceived it:" in with_it.prompt
    assert "the Accord" in with_it.prompt
    assert with_it.prompt.startswith("What this book is to be about:\na brief")
    assert with_it.profile == overview.CONCEPT_OVERVIEW_PROFILE
    assert without.profile == overview.OVERVIEW_PROFILE
    assert with_it.system != without.system, "a settled story needs a public pitch"
    # The shorter task must retain the author's genre requirement even without a dossier.
    no_dossier = overview.render_overview_request("", concept=drawn.render_for_listing())
    assert "LitRPG" in no_dossier.system
    assert "game system" in no_dossier.system
    assert no_dossier.profile == with_it.profile
    assert without == overview.render_overview_request(
        "a brief", WRITER, person="first", concept=None
    )


def test_the_seed_is_told_what_the_world_holds_and_a_second_system_only_when_named() -> None:
    two = concept.Concept.from_payload(_example())
    one_payload = _example()
    one_payload["second_system"] = None
    one = concept.Concept.from_payload(one_payload)
    plain = world_agent.render_seed_request("a listing", WRITER)
    with_one = world_agent.render_seed_request("a listing", WRITER, concept=one)
    with_two = world_agent.render_seed_request("a listing", WRITER, concept=two)
    assert one.render_for_world() in with_one.prompt
    assert "a listing" in with_one.prompt
    assert with_one.system == plain.system, "one system: the seed's task is untouched"
    assert world_agent._SECOND_SYSTEM in (with_two.system or "")
    assert "the Accord" in with_two.prompt
    assert world_agent.render_seed_request("a listing", WRITER, concept=None) == plain


@pytest.mark.parametrize("with_discovery", [False, True])
def test_listing_material_omits_planning_only_fields_without_changing_the_concept(
    with_discovery: bool,
) -> None:
    drawn = concept.Concept.from_payload(_example())
    drawn = replace(
        drawn,
        discovery=discovery.Discovery("A world.", "An opening.", "More magic.")
        if with_discovery
        else None,
        system=replace(drawn.system, look="PRIVATE_DISPLAY", strongest_known="PRIVATE_HORIZON"),
        turn=concept.Turn("PRIVATE_TURN", concept.INSIDE_FIRST_ARC),
        second_system=concept.SecondSystem("PRIVATE_SYSTEM", "PRIVATE_MANNER", "PRIVATE_KEPT"),
        first_arc=replace(drawn.first_arc, middle="PRIVATE_MIDDLE", closes="PRIVATE_ENDING"),
        debts=(concept.Debt("PRIVATE_QUESTION", "PRIVATE_ANSWER", 4),),
    )
    before = drawn.to_text()
    listing = drawn.render_for_listing()
    assert drawn.person_before in listing
    assert drawn.want in listing
    assert "PRIVATE_" not in listing
    # Future plans remain available to the planner, not the world-declaration agent.
    for field in ("PRIVATE_TURN", "PRIVATE_ENDING", "PRIVATE_ANSWER", "PRIVATE_SYSTEM"):
        assert field in json.dumps(drawn.for_outline())
    assert drawn.to_text() == before


def test_listing_preserves_a_turn_that_is_part_of_the_opening_setup() -> None:
    drawn = concept.Concept.from_payload(_example())
    assert drawn.second_system is not None
    listing = drawn.render_for_listing()
    assert drawn.turn.event in listing
    assert drawn.second_system.name in listing
    assert drawn.second_system.kept in listing


@pytest.mark.parametrize("supplied", [False, True])
def test_listing_records_the_profile_it_actually_dispatched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, supplied: bool,
) -> None:
    from litharness import cli

    monkeypatch.setenv("LITHARNESS_FAKE_PAD_CHARS", "400")
    requests, decisions = [], []
    complete = cli._completion_call
    record = SqliteStore.record_decision

    def capture_call(request, **kwargs):
        requests.append(request)
        return complete(request, **kwargs)

    def capture_decision(store, decision, **kwargs):
        decisions.append(decision)
        return record(store, decision, **kwargs)

    monkeypatch.setattr(cli, "_completion_call", capture_call)
    monkeypatch.setattr(SqliteStore, "record_decision", capture_decision)
    db, out = tmp_path / "book.db", tmp_path / "listing"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    args = ["--database", str(db), "listing", "--out", str(out)]
    if supplied:
        path = tmp_path / "concept.json"
        path.write_text(concept.Concept.from_payload(_example()).to_text(), encoding="utf-8")
        args.extend(["--concept", str(path)])
    assert main(args) == EXIT_OK
    expected = overview.CONCEPT_OVERVIEW_PROFILE if supplied else overview.OVERVIEW_PROFILE
    assert requests[0].profile == expected
    assert decisions[-1].profile == expected
    assert decisions[-1].gates[0].rule_or_critic_id == expected
    bundle = json.loads((out / "listing.json").read_text(encoding="utf-8"))
    assert bundle["profile"] == expected


def test_the_outline_plans_the_first_arc_against_the_concept_and_the_old_payload_without() -> None:
    drawn = concept.Concept.from_payload(_example())
    revision = new_book("book", "main", title="Book", scenes=6)
    beats = beats_for(revision, arc_template(6))

    class _Base:
        plan_revision_id = "planrev-1"
        items: tuple = ()

    before = outline.render_outline_request(
        "A premise.",
        beats,
        base=_Base(),  # type: ignore[arg-type]
    )
    after = outline.render_outline_request(
        "A premise.",
        beats,
        base=_Base(),
        concept=None,  # type: ignore[arg-type]
    )
    assert before == after
    with_it = outline.render_outline_request(
        "A premise.",
        beats,
        base=_Base(),
        concept=drawn,  # type: ignore[arg-type]
    )
    payload = json.loads(with_it.prompt)
    assert payload["book_concept"]["first_arc"]["closes"].startswith("he takes it")
    assert payload["book_concept"]["turn"]["when"] == concept.BEFORE_CHAPTER_ONE
    # Carry-over conditions must reach the actual planner request, not just the saved
    # concept: losing this field lets its milestone schedule contradict the intended turn.
    assert payload["book_concept"]["second_system"] == _example()["second_system"]
    assert payload["book_concept"]["system"] == _example()["system"]
    assert payload["book_concept"]["exception"] == drawn.exception
    assert payload["book_concept"]["debts"] == _example()["debts"]
    assert concept.FIRST_ARC_RULE in payload["rules"]
    assert concept.TURN_RULE in payload["rules"]
    later = json.loads(
        outline.render_outline_request(
            "A premise.",
            beats,
            base=_Base(),  # type: ignore[arg-type]
            concept=drawn,
            serial_arc_index=2,
        ).prompt
    )
    assert concept.LATER_ARC_RULE in later["rules"]
    assert later["book_concept"]["second_system"] == _example()["second_system"]
    assert concept.FIRST_ARC_RULE not in later["rules"]
    assert "book_concept" not in json.loads(before.prompt)


def test_a_concept_naming_its_system_with_a_machinery_word_is_caught() -> None:
    """Pilot 24's first concept called its system *the Standing* (`plan/serial-pilot-24.md`
    §1): the listing loop redrew three times and carried the name each time, because the name
    was upstream of it. The check is the listing's own, identity on the declared names and
    capitalised use in the rendered text."""
    plain = concept.Concept.from_payload(_example())
    assert plain.machinery_names() == ()
    payload = _example()
    payload["system"]["name"] = "the Standing"
    assert concept.Concept.from_payload(payload).machinery_names() == ("standing",)
    payload = _example()
    payload["second_system"]["name"] = "The Ladder"
    assert concept.Concept.from_payload(payload).machinery_names() == ("ladder",)
    payload = _example()
    payload["first_use"] = "he reads his sheet and the Rung under it moves"
    assert concept.Concept.from_payload(payload).machinery_names() == ("rung",)


# --- `new --concept`: proposed debts remain in the stored concept ---------------------------


def test_new_persists_the_concept_without_opening_its_proposed_debts(tmp_path: Path) -> None:
    db = tmp_path / "book.db"
    path = tmp_path / "concept.json"
    path.write_text(concept.Concept.from_payload(_example()).to_text(), encoding="utf-8")
    assert main(["--database", str(db), "init"]) == EXIT_OK
    assert (
        main(
            [
                "--database",
                str(db),
                "new",
                "The Far Side",
                "--premise",
                "A premise.",
                "--scenes",
                "6",
                "--concept",
                str(path),
            ]
        )
        == EXIT_OK
    )
    store = SqliteStore.open(db)
    try:
        book_id, branch_id = export.resolve_branch(store, None, None)
        items = store.plan_items(book_id, branch_id)
        stored = concept.concept_of(items)
        assert stored is not None and stored.system.name == "the Tally"
        assert stored.to_jsonable()["debts"] == _example()["debts"]
        assert premise_of(items) == "A premise."
        assert store.promises(book_id, branch_id) == []
    finally:
        store.close()


def test_a_book_created_without_a_concept_carries_none(tmp_path: Path) -> None:
    db = tmp_path / "book.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    assert (
        main(["--database", str(db), "new", "Plain", "--premise", "A premise.", "--scenes", "6"])
        == EXIT_OK
    )
    store = SqliteStore.open(db)
    try:
        book_id, branch_id = export.resolve_branch(store, None, None)
        items = store.plan_items(book_id, branch_id)
        assert concept.concept_of(items) is None
        assert store.promises(book_id, branch_id, open_only=True) == []
    finally:
        store.close()


# --- an unparsed answer spends an attempt ---------------------------------------------------


def _scripted(*answers: dict[str, object] | None):
    """A stand-in for the budget-checked call: each answer is a concept payload, or `None`
    for an answer that came back as prose the schema parser refused."""
    seen: list[object] = []

    def call(request, *, calls, spend):
        seen.append(request)
        answer = answers[min(len(seen) - 1, len(answers) - 1)]
        result = CompletionResult(
            text="Sure, here is the concept in prose." if answer is None else json.dumps(answer),
            provider="scripted",
            model="scripted",
            usage=Usage(output_tokens=3999),
            parsed=answer,
            schema_requested=True,
        )
        return result, ""

    call.seen = seen  # type: ignore[attr-defined]
    return call


def test_an_unparsed_concept_answer_spends_an_attempt_and_the_next_draw_is_kept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Two of the first six concept draws came back unparsed and the command exited on one
    line; the loop is now the retry, and the answer's shape is on stderr for the next one."""
    from litharness import cli

    call = _scripted(_discovery(), None, _example(), {"edits": []})
    monkeypatch.setattr(cli, "_completion_call", call)
    db = tmp_path / "book.db"
    out = tmp_path / "concept"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    capsys.readouterr()
    argv = ["--database", str(db), "concept", "--writer", "ferreira", "--scenes", "6"]
    assert main([*argv, "--out", str(out)]) == EXIT_OK
    err = capsys.readouterr().err
    assert "came back unparsed" in err and "3999 output tokens" in err
    assert "Sure, here is" in err, "the answer's first words are on stderr"
    assert len(call.seen) == 4  # type: ignore[attr-defined]
    assert (out / "concept.json").exists()
    failed = json.loads((out / "concept-trace-1.json").read_text())
    succeeded = json.loads((out / "concept-trace-2.json").read_text())
    assert failed["response"] == "Sure, here is the concept in prose."
    assert failed["request"] == succeeded["request"]
    assert not failed["contains_exemplar_material"]


def test_a_concept_that_never_parses_is_a_fault_after_the_bounded_draws(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from litharness import cli

    call = _scripted(_discovery(), *([None] * cli.CONCEPT_DRAW_ATTEMPTS))
    monkeypatch.setattr(cli, "_completion_call", call)
    db = tmp_path / "book.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    capsys.readouterr()
    argv = ["--database", str(db), "concept", "--writer", "ferreira", "--scenes", "6"]
    assert main([*argv, "--out", str(tmp_path / "concept")]) == EXIT_FAULT
    err = capsys.readouterr().err
    assert len(call.seen) == cli.CONCEPT_DRAW_ATTEMPTS + 1  # type: ignore[attr-defined]
    assert f"no concept parsed in {cli.CONCEPT_DRAW_ATTEMPTS} draw(s)" in err
    assert not (tmp_path / "concept" / "concept.json").exists()


def test_distinct_from_is_only_an_invention_constraint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from litharness import cli

    old = _example()
    old["person_before"] = "PREVIOUS_PROTAGONIST_BOUNDARY"
    path = tmp_path / "previous.json"
    path.write_text(concept.Concept.from_payload(old).to_text(), encoding="utf-8")
    call = _scripted(_discovery(), _example(), {"edits": []})
    monkeypatch.setattr(cli, "_completion_call", call)
    output = tmp_path / "new-concept"
    assert main([
        "--database", str(tmp_path / "new.db"), "concept", "--brief", "Fresh adventure.",
        "--writer", "ferreira", "--distinct-from", str(path), "--out", str(output),
    ]) == EXIT_OK
    requests = call.seen  # type: ignore[attr-defined]
    assert "PREVIOUS_PROTAGONIST_BOUNDARY" in requests[0].prompt
    assert all("PREVIOUS_PROTAGONIST_BOUNDARY" not in request.prompt for request in requests[1:])
    saved = concept.Concept.from_text((output / "concept.json").read_text(encoding="utf-8"))
    assert saved.author_brief == "Fresh adventure."
    assert "PREVIOUS_PROTAGONIST_BOUNDARY" not in saved.to_text()
    assert "PREVIOUS_PROTAGONIST_BOUNDARY" not in world_agent.render_seed_request(
        "New listing.", concept=saved
    ).prompt


def test_a_bad_distinct_from_file_refuses_before_opening_a_store(tmp_path: Path) -> None:
    database = tmp_path / "new.db"
    with pytest.raises(SystemExit, match=r"missing\.json"):
        main([
            "--database", str(database), "concept",
            "--distinct-from", str(tmp_path / "missing.json"),
        ])
    assert not database.exists()


def test_stored_v3_discovery_retains_its_original_direction() -> None:
    old = discovery.Discovery.from_payload({**_discovery(), "version": "magical-discovery.v3"})
    restored = discovery.Discovery.from_payload(old.to_jsonable())
    assert restored == old
    assert "Make discovery and the practiced use of magic drive advancement" in restored.render()
    assert discovery.DIRECTION not in restored.render()


def test_stored_v4_discovery_keeps_its_direction_when_developed_again() -> None:
    payload = {**_discovery(), "version": "magical-discovery.v4"}
    original_direction = (
        "Create a LitRPG fantasy experience in portal fantasy, isekai, or system apocalypse, or "
        "a combination, unless the author's brief calls for something else: an unfamiliar world "
        "worth exploring and powers the character wants to acquire and use. Let the chosen "
        "magic system determine how advancement is earned through the story's events, including "
        "discovery, conflict, exploration, choices or practice. Develop what an early gain lets "
        "the protagonist accomplish for a personal pursuit, and what makes a further capability "
        "desirable. Let them experience and use a reward as well as encounter its limitations."
    )
    saved = discovery.Discovery.from_payload(payload)
    restored = discovery.Discovery.from_payload(saved.to_jsonable())
    assert restored.to_jsonable() == payload
    assert restored.render().splitlines()[0] == (
        f"Intended fantasy experience (magical-discovery.v4): {original_direction}"
    )
    request = concept.render_concept_request("Keep this story.", scenes=6, discovery=restored)
    assert restored.render() in request.prompt
    assert discovery.DIRECTION not in request.system + request.prompt


def _discovery() -> dict[str, object]:
    return {
        "world": "Reefs float through the mountain passes and carry living weather.",
        "opening": "A gardener wakes a dormant seed to reach a reef before it departs.",
        "growth": "She can learn to grow shelter in the air and travel with the reefs.",
    }


def test_discovery_precedes_mechanics_and_survives_cli_persistence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from litharness import cli
    from litharness.application.planner import packet_for

    # A second-stage answer tries to replace the treatment; the first stage owns it.
    answer = {**_example(), "discovery": dict.fromkeys(_discovery(), "replacement")}
    call = _scripted(_discovery(), answer, {"edits": []})
    monkeypatch.setattr(cli, "_completion_call", call)
    db, out = tmp_path / "book.db", tmp_path / "concept"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    assert (
        main(
            [
                "--database",
                str(db),
                "concept",
                "--brief",
                "A gardener explores the sky.",
                "--scenes",
                "6",
                "--out",
                str(out),
            ]
        )
        == EXIT_OK
    )
    first, second, preparation = call.seen  # type: ignore[attr-defined]
    assert first.profile == discovery.PROFILE
    assert first.schema is discovery.SCHEMA
    assert second.profile == concept.DISCOVERY_CONCEPT_PROFILE
    assert preparation.profile == concept.precision.PROFILE
    assert str(_discovery()["world"]) in second.prompt
    assert "A gardener explores the sky." in first.prompt
    retained = concept.Concept.from_text((out / "concept.json").read_text(encoding="utf-8"))
    assert retained.discovery == discovery.Discovery.from_payload(_discovery())
    assert retained.author_brief == "A gardener explores the sky."
    assert retained.first_arc.opens == retained.discovery.opening
    assert retained.render().count(retained.discovery.opening) == 1
    assert json.loads((out / "discovery-trace.json").read_text())["response"] == json.dumps(
        _discovery()
    )
    assert (
        main(
            [
                "--database",
                str(db),
                "new",
                "Reefs",
                "--premise",
                "A gardener explores the sky.",
                "--scenes",
                "6",
                "--concept",
                str(out / "concept.json"),
            ]
        )
        == EXIT_OK
    )
    with SqliteStore.open(db) as store:
        book_id, branch_id = export.resolve_branch(store, None, None)
        stored = concept.concept_of(store.plan_items(book_id, branch_id))
        assert stored == retained
        head = store.head(book_id, branch_id)
        assert head is not None
        beat = beats_for(head, arc_template(6))[0]
        packet = packet_for(store, head, beat)
        assert f"Author's original book brief:\n{retained.author_brief}" in packet.render()
        assert retained.discovery.world not in packet.render()
        assert retained.discovery.growth not in packet.render()
        assert retained.discovery.opening not in packet.render()
        assert str(_discovery()["opening"]) not in "\n".join(
            item.text for item in packet.sections.get("facts", ())
        )


@pytest.mark.parametrize("answer", [None, {}, {**_discovery(), "growth": ""}])
def test_missing_discovery_stops_before_mechanics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, answer: dict[str, object] | None
) -> None:
    from litharness import cli

    call = _scripted(answer)
    monkeypatch.setattr(cli, "_completion_call", call)
    db, out = tmp_path / "book.db", tmp_path / "concept"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    assert main(["--database", str(db), "concept", "--out", str(out)]) == EXIT_FAULT
    assert len(call.seen) == 1  # type: ignore[attr-defined]
    assert not (out / "concept.json").exists()
    assert (out / "discovery-trace.json").exists()


def test_reserved_discovery_name_stops_before_unrepairable_mechanical_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from litharness import cli

    answer = {**_discovery(), "growth": "She learns to use the Standing."}
    call = _scripted(answer)
    monkeypatch.setattr(cli, "_completion_call", call)
    db, out = tmp_path / "book.db", tmp_path / "concept"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    assert main(["--database", str(db), "concept", "--out", str(out)]) == EXIT_FAULT
    assert len(call.seen) == 1  # type: ignore[attr-defined]
    assert "reserved names: standing" in capsys.readouterr().err
    assert not (out / "concept.json").exists()
    assert json.loads((out / "discovery-trace.json").read_text())["response"] == json.dumps(answer)


@pytest.mark.parametrize("field", ["world", "opening", "growth"])
def test_invention_validation_rejects_reserved_names_without_breaking_stored_reads(
    field: str,
) -> None:
    payload = {**_discovery(), field: "She learns to use the Standing."}
    retained = discovery.Discovery.from_payload(payload)
    assert getattr(retained, field) == payload[field]
    with pytest.raises(ValueError, match="reserved names: standing"):
        discovery.Discovery.from_invention(payload)


def test_invention_validation_preserves_valid_treatment() -> None:
    payload = _discovery()
    assert discovery.Discovery.from_invention(payload) == discovery.Discovery.from_payload(payload)


def test_discovery_material_reaches_listing_and_later_arcs_with_scoped_world_inputs() -> None:
    payload = {**_example(), "discovery": _discovery()}
    drawn = concept.Concept.from_payload(payload)
    assert drawn.discovery is not None
    listing = drawn.render_for_listing()
    for value in (drawn.discovery.world, drawn.discovery.opening, drawn.discovery.growth):
        assert value in listing
    assert "These are story intentions" not in listing
    assert drawn.discovery.world in world_agent.render_seed_request("listing", concept=drawn).prompt
    for request in (
        discovery.render_request(""),
        concept.render_concept_request("", scenes=6, discovery=drawn.discovery),
        world_agent.render_seed_request("listing", concept=drawn),
        world_agent.render_grow_request("chapter", logical_id="scene-1", concept=drawn),
    ):
        assert request.system.count(house.QUANTITY_DETAIL) == 1

    class Base:
        plan_revision_id = "plan-1"
        items: tuple[lc.PlanItem, ...] = ()

    base = Base()
    revision = new_book("b", "main", title="Book", scenes=6)
    for arc_index in (1, 2, 5):
        request = outline.render_outline_request(
            "listing",
            beats_for(revision, arc_template(6)),
            base=base,  # type: ignore[arg-type]
            concept=drawn,
            serial_arc_index=arc_index,
            seed={"level": 1},
        )
        parsed = json.loads(request.prompt)
        assert request.system.count(house.QUANTITY_DETAIL) == 1
        assert parsed["book_concept"]["discovery"] == {
            "version": drawn.discovery.to_jsonable()["version"],
            "world": drawn.discovery.world, "growth": drawn.discovery.growth,
        }
        assert concept.DISCOVERY_ARC_RULE in parsed["rules"]
        assert not any("numbers must actually move" in rule for rule in parsed["rules"])


def test_inhabited_world_survives_development_and_seed_without_future_discoveries() -> None:
    source = discovery.Discovery.from_invention({
        "world": (
            "An old hill settlement surrounds a sealed kiln. Its inhabitants repair tiles "
            "for homes elsewhere; worn trade marks remain beneath newer glazes. Visitors "
            "can compare those marks with tiles offered for exchange. The makers disagree "
            "about who built the kiln; its original purpose remains unknown."
        ),
        "opening": "OPENING_ACTION: the gardener exchanges a cutting and finds a route home.",
        "growth": "CAPABILITY_GOAL: growing a shelter that can travel between the hills.",
    })
    brief = "Preserve the gardener's ordinary starting abilities and untranslated local script."
    answer = {**_example(), "discovery": dict.fromkeys(_discovery(), "REPLACEMENT_WORLD")}
    developed = concept.Concept.from_development(answer, source, author_brief=brief)
    restored = concept.Concept.from_text(developed.to_text())
    seed = world_agent.render_seed_request(
        "A gardener reaches an unfamiliar settlement.", concept=restored,
    )

    assert restored.discovery == source
    assert restored.first_arc.opens == source.opening
    assert restored.author_brief == brief
    assert seed.profile == "architect.seed.v3"
    assert source.world in seed.prompt
    assert brief in seed.prompt
    assert restored.system.manner in seed.prompt
    assert restored.system.pays in seed.prompt
    for future_or_replaced in (source.opening, source.growth, "REPLACEMENT_WORLD"):
        assert future_or_replaced not in seed.prompt
    assert restored.to_text() == developed.to_text()


@pytest.mark.parametrize("with_discovery", [False, True])
@pytest.mark.parametrize("turn_before_opening", [False, True])
def test_future_story_fields_cannot_return_as_world_declaration_material(
    with_discovery: bool, turn_before_opening: bool,
) -> None:
    drawn = concept.Concept.from_payload(_example())
    drawn = replace(
        drawn,
        discovery=discovery.Discovery("SETTING_MARKER", "OPENING_MARKER", "GROWTH_MARKER")
        if with_discovery else None,
        first_use="FIRST_USE_MARKER",
        want="WANT_MARKER",
        threat=replace(drawn.threat, first_reach="FIRST_REACH_MARKER"),
        turn=concept.Turn(
            "TURN_MARKER",
            concept.BEFORE_CHAPTER_ONE if turn_before_opening else concept.INSIDE_FIRST_ARC,
        ),
        first_arc=concept.FirstArc("ARC_START_MARKER", "ARC_MIDDLE_MARKER", "ARC_END_MARKER"),
        debts=(
            concept.Debt("DEBT_SUBJECT_MARKER", "DEBT_ANSWER_MARKER", 4),
            concept.Debt("SECOND_DEBT_MARKER", "SECOND_ANSWER_MARKER", 5),
        ),
        author_brief="AUTHOR_BRIEF_MARKER",
    )
    original = drawn.to_text()
    seed = world_agent.render_seed_request("LISTING_MARKER", concept=drawn)
    grow = world_agent.render_grow_request("CHAPTER_MARKER", logical_id="s1", concept=drawn)
    for marker in (
        "FIRST_USE_MARKER", "WANT_MARKER", "FIRST_REACH_MARKER", "ARC_START_MARKER",
        "ARC_MIDDLE_MARKER", "ARC_END_MARKER", "DEBT_SUBJECT_MARKER", "DEBT_ANSWER_MARKER",
        "SECOND_DEBT_MARKER", "SECOND_ANSWER_MARKER",
    ):
        assert marker not in seed.prompt
        assert marker not in grow.prompt
        assert (marker in json.dumps(drawn.for_outline())) is (
            marker not in {"FIRST_USE_MARKER", "FIRST_REACH_MARKER", "ARC_START_MARKER"}
        )
    assert "LISTING_MARKER" in seed.prompt
    assert "AUTHOR_BRIEF_MARKER" in seed.prompt
    assert "AUTHOR_BRIEF_MARKER" in grow.prompt
    assert ("TURN_MARKER" in seed.prompt) is turn_before_opening
    assert drawn.system.name in seed.prompt
    assert drawn.system.pays in seed.prompt
    assert drawn.person_before in seed.prompt
    assert drawn.threat.what in seed.prompt
    assert drawn.second_system is not None
    assert drawn.second_system.kept in seed.prompt
    if with_discovery:
        assert "SETTING_MARKER" in seed.prompt
        for marker in ("OPENING_MARKER", "GROWTH_MARKER"):
            assert marker not in seed.prompt
            assert (marker in json.dumps(drawn.for_outline())) is (marker == "GROWTH_MARKER")
    assert grow.prompt.startswith("The chapter just drafted (s1):\n\nCHAPTER_MARKER")
    assert "TURN_MARKER" not in grow.prompt
    assert drawn.person_before not in grow.prompt
    assert "OPENING_MARKER" not in grow.prompt
    assert "GROWTH_MARKER" not in grow.prompt
    assert concept.concept_of((drawn.plan_item(),)) == drawn
    assert drawn.to_text() == original


def test_a_supplied_treatment_owns_development_despite_different_writer_preferences() -> None:
    drawn = concept.Concept.from_payload({**_example(), "discovery": _discovery()})
    assert drawn.discovery is not None
    original = drawn.to_text()
    brief = "Keep the gardener's pursuit of the sky reefs."
    development = concept.render_concept_request(brief, scenes=6, discovery=drawn.discovery)
    seed = world_agent.render_seed_request("listing", concept=drawn)
    grow = world_agent.render_grow_request("chapter", logical_id="scene-1", concept=drawn)
    for writer in writers_domain.CAST.values():
        assert concept.render_concept_request(
            brief, writer, scenes=6, discovery=drawn.discovery
        ) == development
        assert world_agent.render_seed_request("listing", writer, concept=drawn) == seed
        assert world_agent.render_grow_request(
            "chapter", logical_id="scene-1", writer=writer, concept=drawn
        ) == grow
        # The writer still participates in initial invention; no accepted dossier is edited.
        assert discovery.render_request(brief, writer).system.startswith(writer.render())
    assert brief in development.prompt
    assert drawn.discovery.render() in development.prompt
    assert drawn.to_text() == original
    assert seed.allowed_tools == grow.allowed_tools == world_agent.ALLOWED_TOOLS
    legacy = concept.Concept.from_payload(_example())
    for prior in (None, legacy):
        assert world_agent.render_seed_request("listing", WRITER, concept=prior).system.startswith(
            WRITER.render()
        )
        assert world_agent.render_grow_request(
            "chapter", logical_id="scene-1", writer=WRITER, concept=prior
        ).system.startswith(WRITER.render())


def test_world_mechanics_do_not_require_institutional_conflict_or_early_grant_exposition() -> None:
    request = world_agent.render_seed_request("listing")
    assert "price it or withhold it" not in request.system
    assert "the book is better when" not in request.system
    assert "five to eight grants per system" in request.system
    assert "require its introduction in chapter one" in request.system


@pytest.mark.parametrize("author_mechanics", [
    "All spells require a separately acquired awareness ability before use.",
    "Basic casting needs no separate awareness ability.",
])
def test_fresh_world_cli_preserves_explicit_author_mechanics_in_the_seed_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, author_mechanics: str,
) -> None:
    from litharness import cli

    drawn = replace(
        concept.Concept.from_payload({**_example(), "discovery": _discovery()}),
        author_brief=author_mechanics,
    )
    path = tmp_path / "concept.json"
    path.write_text(drawn.to_text(), encoding="utf-8")
    original = path.read_bytes()
    db = tmp_path / "book.db"
    monkeypatch.setenv("LITHARNESS_DATABASE", str(db))
    call = _scripted({})
    monkeypatch.setattr(cli, "_completion_call", call)
    base = ["--database", str(db), "--writer", "ferreira"]
    assert main([
        *base, "new", "Book", "--premise", "FROZEN_LISTING", "--concept", str(path),
    ]) == EXIT_OK
    assert not call.seen  # type: ignore[attr-defined]
    assert main([*base, "architect", "seed"]) == EXIT_OK
    assert call.seen == [  # type: ignore[attr-defined]
        world_agent.render_seed_request("FROZEN_LISTING", WRITER, concept=drawn),
    ]
    assert author_mechanics in call.seen[0].prompt  # type: ignore[attr-defined]
    with SqliteStore.open_read_only(db) as store:
        book, branch, _ = store.branches()[0]
        assert concept.concept_of(store.plan_items(book, branch)) == drawn
        assert not store.state_records(book, branch)
    assert path.read_bytes() == original


def test_legacy_concepts_are_not_rewritten_and_bad_discovery_does_not_disappear() -> None:
    legacy = concept.Concept.from_payload(_example())
    assert legacy.discovery is None
    assert "discovery" not in legacy.to_jsonable()
    assert "magical-discovery" not in legacy.render()
    for bad in (None, {}, {**_discovery(), "version": "unknown"}):
        with pytest.raises(concept.MalformedConcept, match="discovery"):
            concept.Concept.from_payload({**_example(), "discovery": bad})
    v1 = discovery.Discovery.from_payload({**_discovery(), "version": "magical-discovery.v1"})
    assert v1.version == v1.to_jsonable()["version"] == "magical-discovery.v1"
    assert "Create a magical fantasy experience with progression" in v1.render()
    assert discovery.DIRECTION not in v1.render()


def test_stored_v2_treatment_keeps_its_direction_when_developed_again() -> None:
    payload = {**_discovery(), "version": "magical-discovery.v2"}
    treatment = discovery.Discovery.from_payload(payload)
    prior_direction = (
        "Create a LitRPG fantasy experience: an unfamiliar world worth exploring, magic "
        "someone can discover and use, and growing capability that opens possibilities "
        "they want to pursue. Progression develops the character's own magical or physical "
        "capabilities; the game system tracks those changes independently of employment, "
        "licences or institutional rank. Make discovery and the practiced use of magic drive "
        "advancement. Let the character act on curiosity and desire as well as danger, within "
        "the author's specific brief."
    )
    assert treatment.render().splitlines()[0] == (
        f"Intended fantasy experience (magical-discovery.v2): {prior_direction}"
    )
    request = concept.render_concept_request("Keep this story.", scenes=6, discovery=treatment)
    assert treatment.render() in request.prompt
    assert "portal fantasy, isekai, or system apocalypse" not in request.system + request.prompt
    assert request.profile == concept.DISCOVERY_CONCEPT_PROFILE
    assert treatment.to_jsonable() == payload


@pytest.mark.parametrize("refused_profile", [discovery.PROFILE, concept.DISCOVERY_CONCEPT_PROFILE])
def test_either_stage_refusal_stops_without_publishing_a_concept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, refused_profile: str
) -> None:
    from litharness import cli

    scripted = _scripted(_discovery())
    seen = []

    def call(request, *, calls, spend):
        seen.append(request.profile)
        if request.profile == refused_profile:
            return None, "quota exhausted"
        return scripted(request, calls=calls, spend=spend)

    monkeypatch.setattr(cli, "_completion_call", call)
    db, out = tmp_path / "book.db", tmp_path / "concept"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    assert main(["--database", str(db), "concept", "--out", str(out)]) == EXIT_FAULT
    assert seen[-1] == refused_profile
    assert not (out / "concept.json").exists()


def test_outline_handler_accepts_discovery_action_without_invented_stat_movement(
    tmp_path: Path,
) -> None:
    from litharness.application.outline import make_outline_handler
    from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID
    from tests.test_outline import START, StubPlanner, _job, a_book
    from tests.test_scene_brief import outlined_payload

    drawn = concept.Concept.from_payload({**_example(), "discovery": _discovery()})
    with SqliteStore.open(tmp_path / "outline.db") as store:
        a_book(store, scenes=6, extra_plan_items=(drawn.plan_item(),))
        response = outlined_payload()
        registry = StubPlanner(response)
        before = store.plan_revision(BOOK_ID, BRANCH_ID)
        make_outline_handler(registry, store, PROJECT_ID)(_job(store), START)
        after = store.plan_revision(BOOK_ID, BRANCH_ID)
        assert before is not None and after is not None
        assert before.plan_revision_id != after.plan_revision_id
        assert len([item for item in after.items if item.kind is lc.PlanKind.SCENE_PLAN]) == 6
        assert concept.concept_of(after.items) == drawn
        assert not any(
            row.record_id.startswith("milestone-")
            for row in store.state_records(BOOK_ID, BRANCH_ID)
        )
