"""The concept stage: one book invented before its listing, and what each stage below is told.

Stage-0 §197. Draw 4 of pilot 21 (`plan/serial-pilot-21.md` §5.4) found no horizon a reader
could feel and the listing at fault; nothing above the listing existed. These tests hold the
shape of the fix: the schema can express the operator's example premise (a turn, two systems,
grants kept across them); the concept is a plan item the scene writer never sees; the listing,
the seed and the outline are each told it and render byte-identically without it; `new` opens
its debts on the promise ledger. No model call, no network.
"""

from __future__ import annotations

import json
from pathlib import Path

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application import concept, export, outline, overview, world_agent
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


# --- where it lives ------------------------------------------------------------------------


def test_the_concept_is_a_book_plan_item_the_scene_writer_never_sees() -> None:
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
    assert with_it.system == without.system, "the task's demands are untouched"
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
    assert with_one.prompt.startswith("The listing this book was sold on:\n\na listing")
    assert "What the book is to become, which the world has to be able to hold:" in with_one.prompt
    assert with_one.system == plain.system, "one system: the seed's task is untouched"
    assert world_agent._SECOND_SYSTEM in (with_two.system or "")
    assert "the Accord" in with_two.prompt
    assert world_agent.render_seed_request("a listing", WRITER, concept=None) == plain


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


def test_the_debts_are_the_shape_the_promise_loader_reads() -> None:
    drawn = concept.Concept.from_payload(_example())
    entries = drawn.promise_entries()
    assert [entry["subject"] for entry in entries] == [
        "the silence of the Tally",
        "the eleven years",
    ]
    assert all({"subject", "description", "due_scene"} <= set(entry) for entry in entries)


# --- `new --concept`: persisted, and its debts opened before scene one ----------------------


def test_new_persists_the_concept_and_opens_its_debts_on_the_ledger(tmp_path: Path) -> None:
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
        assert premise_of(items) == "A premise."
        owed = store.promises(book_id, branch_id, open_only=True)
        # Subjects are normalised by the loader, exactly as `--promises` entries are.
        assert sorted(promise.subject for promise in owed) == [
            "the_eleven_years",
            "the_silence_of_the_tally",
        ]
        assert all(promise.due_key is not None for promise in owed)
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

    call = _scripted(None, _example())
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
    assert len(call.seen) == 2  # type: ignore[attr-defined]
    assert (out / "concept.json").exists()


def test_a_concept_that_never_parses_is_a_fault_after_the_bounded_draws(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from litharness import cli

    call = _scripted(None)
    monkeypatch.setattr(cli, "_completion_call", call)
    db = tmp_path / "book.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    capsys.readouterr()
    argv = ["--database", str(db), "concept", "--writer", "ferreira", "--scenes", "6"]
    assert main([*argv, "--out", str(tmp_path / "concept")]) == EXIT_FAULT
    err = capsys.readouterr().err
    assert len(call.seen) == cli.CONCEPT_DRAW_ATTEMPTS  # type: ignore[attr-defined]
    assert f"no concept parsed in {cli.CONCEPT_DRAW_ATTEMPTS} draw(s)" in err
    assert not (tmp_path / "concept" / "concept.json").exists()
