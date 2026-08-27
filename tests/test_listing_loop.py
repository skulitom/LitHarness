"""The listing loop and the title lookup: what is decided in code, and what is only reported.

**One property is worth more than the rest of this file.** `application/titles.py` exists
because the operator asked for a check that a title is free to use, and the standing rule
(§61(5), §105.1) is that no model ranks or selects unless the containment for it exists. The
containment here is that the verdict is *arithmetic over what came back*: an exact normalised
title match, counted in code, over an answer that has no slot for an opinion. So the tests that
matter are the ones that would fail if a verdict ever came out of the answer instead — a
`works` list the model filled with near misses must not read as taken, and an answer with no
search behind it must not read as free.

Everything here is dictionary and string handling. No database, no model call, no network.
"""

from __future__ import annotations

import json

import pytest

from litharness.application import overview, readers, titles
from litharness.cli import EXIT_OK, main
from litharness.domain import writers as writers_domain

WRITER = writers_domain.CAST["ferreira"]


# --- the lookup decides nothing -------------------------------------------------------


def test_the_lookup_is_never_asked_whether_a_title_is_good() -> None:
    """The schema has no verdict slot, and that is the whole containment.

    A field a model can fill with an opinion is a verdict channel, and §89 measured one of
    those running 4,676x position over text. If this list ever grows a boolean, the check has
    become a judge.
    """
    properties = titles.FINDINGS_SCHEMA["properties"]
    assert set(properties) == {"searched", "works"}
    work = properties["works"]["items"]["properties"]
    assert set(work) == {"title", "kind", "where", "url"}
    for spec in work.values():
        assert spec["type"] == "string"


def test_the_lookup_holds_one_read_only_tool_and_no_shell() -> None:
    request = titles.render_check_request("The Cinder Road")
    assert request.allowed_tools == ("WebSearch",)
    assert "cinder" in request.prompt.lower()


def test_an_exact_match_is_taken_and_a_near_miss_is_only_reported() -> None:
    """Deciding that `Cinder Roads` is too close to `The Cinder Road` is a judgment.

    The near miss reaches a person through `near`, changes no verdict, and is counted by
    nothing — which is `platform_priors.panel`'s discipline for a tripwire counter, at the
    grain of one title.
    """
    found = titles.read(
        "The Cinder Road",
        {
            "searched": ["the cinder road"],
            "works": [{"title": "Cinder Roads", "kind": "novel", "where": "somebody"}],
        },
        searches=2,
    )
    assert found.verdict == titles.FREE
    assert found.free
    assert [item.title for item in found.near] == ["Cinder Roads"]
    assert found.collisions == ()

    collided = titles.read(
        "The Cinder Road",
        {
            "searched": ["the cinder road"],
            "works": [{"title": "the CINDER road!", "kind": "web serial", "where": "RR"}],
        },
        searches=1,
    )
    assert collided.verdict == titles.TAKEN
    assert not collided.free
    assert len(collided.collisions) == 1


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("The Cinder Road", "the cinder road"),
        ("The Cinder Road", "The Cinder Road!"),
        ("The  Cinder   Road", "The Cinder Road"),
    ],
)
def test_one_title_written_three_ways_normalises_to_one_title(left: str, right: str) -> None:
    assert titles.normalise(left) == titles.normalise(right)


def test_a_curly_apostrophe_and_a_straight_one_are_the_same_title() -> None:
    """Built from a code point rather than typed, so this file stays ASCII.

    `clean_title` strips a quotation mark that *wraps* a title and has no business touching
    one inside it, so the folding has to happen here.
    """
    curly = "Ash " + chr(0x2019) + "n Iron"
    assert titles.normalise(curly) == titles.normalise("Ash 'n Iron")


def test_two_different_titles_do_not_normalise_together() -> None:
    """Normalisation drops case, punctuation and spacing and stops there."""
    assert titles.normalise("The Cinder Road") != titles.normalise("Cinder Road")
    assert titles.normalise("Iron and Ash") != titles.normalise("Ash and Iron")


def test_an_answer_with_no_search_behind_it_is_unknown_rather_than_free() -> None:
    """The one failure that would make this check theatre.

    A model that answers "nothing found" without looking is indistinguishable from a free
    title on the text alone. `searches` comes from the transport's own record, so an unsearched
    answer lands in the third verdict rather than the good one.
    """
    quiet = titles.read("The Cinder Road", {"searched": [], "works": []}, searches=0)
    assert quiet.verdict == titles.UNKNOWN
    assert not quiet.free
    assert "no web search" in quiet.note


def test_a_refused_call_is_unknown_and_carries_the_reason() -> None:
    refused = titles.read("The Cinder Road", None, refusal="the daily budget refused the call")
    assert refused.verdict == titles.UNKNOWN
    assert "budget" in refused.note


def test_the_search_count_is_read_from_wherever_the_transport_reports_it() -> None:
    """Shape-tolerant on purpose: `application` may not know a provider's envelope layout."""
    envelope = {
        "usage": {"server_tool_use": {"web_search_requests": 0}},
        "modelUsage": {
            "claude-haiku-4-5": {"webSearchRequests": 2},
            "claude-opus-5": {"webSearchRequests": 0},
        },
    }
    assert titles.searches_reported(envelope) == 2
    assert titles.searches_reported({}) == 0
    assert titles.searches_reported(None) == 0


def test_a_malformed_work_row_is_dropped_rather_than_counted() -> None:
    """A row with no title cannot collide with anything, and must not be a phantom near miss."""
    found = titles.read(
        "The Cinder Road",
        {"searched": ["x"], "works": [{"kind": "novel"}, "not a mapping", {"title": "  "}]},
        searches=1,
    )
    assert found.verdict == titles.FREE
    assert found.collisions == ()
    assert found.near == ()


# --- what the writer is told when a title is taken -------------------------------------


def test_a_taken_title_reaches_the_writer_as_a_prohibition_and_not_as_a_rule() -> None:
    """It goes in the prompt beside the listing, never into the job.

    A fact about the world belongs with the material; put in the system message it becomes a
    standing rule about titles for every book this system ever writes.
    """
    request = overview.render_title_request("a listing", WRITER, ("The Cinder Road",))
    assert "The Cinder Road" in request.prompt
    assert "The Cinder Road" not in (request.system or "")
    assert "cannot be this one" in request.prompt


def test_with_nothing_taken_the_title_call_is_what_it_always_was() -> None:
    plain = overview.render_title_request("a listing", WRITER)
    assert plain.prompt == "The listing:\n\na listing"


# --- the title the browsing pool is shown ----------------------------------------------


def test_the_browsing_reader_sees_the_title_above_the_blurb_when_there_is_one() -> None:
    reader = readers.pool(readers.MEASUREMENT)[0]
    with_title = readers.render_start_request(reader, "a listing", "The Cinder Road")
    assert with_title.prompt.startswith("The Cinder Road\n\na listing")


def test_the_no_title_arm_is_byte_identical_to_every_round_before_titles_existed() -> None:
    """The control has to be the same code path, or the comparison is between two scripts."""
    reader = readers.pool(readers.MEASUREMENT)[0]
    assert (
        readers.render_start_request(reader, "a listing", "").prompt
        == readers.render_start_request(reader, "a listing").prompt
    )


def test_a_steering_reader_still_may_not_measure() -> None:
    steering = readers.pool(readers.STEERING)[0]
    with pytest.raises(ValueError):
        readers.render_start_request(steering, "a listing", "The Cinder Road")


# --- the loop, end to end on the fake --------------------------------------------------


@pytest.fixture
def fake(monkeypatch) -> None:
    """The one road to a model-free run. Setting it *is* the statement that the fake is on."""
    monkeypatch.setenv("LITHARNESS_FAKE_PAD_CHARS", "400")


def test_the_loop_writes_a_listing_a_title_and_a_bundle(fake, tmp_path, capsys) -> None:
    db = tmp_path / "listing.db"
    out = tmp_path / "shelf"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    capsys.readouterr()
    assert (
        main(
            [
                "--database",
                str(db),
                "listing",
                "--brief",
                "a locksmith who can hear what a door remembers",
                "--writer",
                "ferreira",
                "--out",
                str(out),
                "--json",
            ]
        )
        == EXIT_OK
    )
    bundle = json.loads(capsys.readouterr().out)
    assert bundle["writer"] == "ferreira"
    assert bundle["listing"]
    assert bundle["title"]
    assert (out / "listing.txt").read_text(encoding="utf-8").strip() == bundle["listing"]
    assert (out / "title.txt").read_text(encoding="utf-8").strip() == bundle["title"]
    assert json.loads((out / "listing.json").read_text(encoding="utf-8")) == bundle


def test_the_loop_carries_its_own_title_into_the_book_it_creates(fake, tmp_path, capsys) -> None:
    """The hand-move this loop had at the end, and §126 is why it is gone.

    A generated title that a person retypes into `new` is a human in the production loop.
    """
    db = tmp_path / "listing.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    capsys.readouterr()
    assert (
        main(["--database", str(db), "listing", "--writer", "vance", "--scenes", "24", "--json"])
        == EXIT_OK
    )
    printed = capsys.readouterr().out
    bundle = json.loads(printed[: printed.index("\n}") + 2])

    from litharness.adapters.sqlite_store import SqliteStore
    from litharness.domain.plans import premise_of

    with SqliteStore.open(db) as store:
        books = store.branches()
        assert len(books) == 1
        book_id, branch_id, _ = books[0]
        head = store.head(book_id, branch_id)
        assert head is not None
        assert head.children_of(None)[0].title == bundle["title"]
        assert premise_of(store.plan_items(book_id, branch_id)) == bundle["listing"]
        assert sum(1 for node in head.nodes if node.kind.value == "scene") == 24


def test_the_architect_seeds_under_the_listing_the_book_was_sold_on(fake, tmp_path) -> None:
    """No `--overview` file: the premise the book was created under is the listing."""
    db = tmp_path / "listing.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    assert (
        main(["--database", str(db), "listing", "--writer", "okonjo", "--scenes", "24"]) == EXIT_OK
    )
    assert main(["--database", str(db), "architect", "seed"]) == EXIT_OK


def test_a_listing_command_with_an_unknown_writer_is_refused_before_any_call(
    fake, tmp_path, capsys
) -> None:
    db = tmp_path / "listing.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    assert main(["--database", str(db), "listing", "--writer", "nobody"]) != EXIT_OK
    assert "the cast is" in capsys.readouterr().err
