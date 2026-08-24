"""The comprehension screen: four readers, one paragraph, and a count that refuses.

`plan/handoff-clarity-first.md` boundary 5 — *"No premise reaches the operator unscreened,
ever"* — graded end to end. The arithmetic half is hermetic: `ScreenResult` is built from
answers a test writes, so what passes and what fails is checked without a provider anywhere.
The wiring half runs `forge` through `FakeProvider` with the whole call sequence scripted, which
is the only way to grade "one fresh regeneration and one re-screen" as a number of calls rather
than as an intention.

What is deliberately not graded here is whether the four readers are *good* readers. That is a
validity question about an instrument, it belongs to `research/quality-measurement`, and the
screen makes no claim that needs it: it reports which words a reader said they could not follow
and refuses on the count, which is E6's shape (name what is there) rather than a verdict.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from litharness.application import architect, comprehension
from litharness.cli import main
from litharness.domain import house
from tests.test_architect import PREMISE, forge_script, reader_answer, world


def answers(**by_reader: Any) -> dict[str, Any]:
    """The four readers' parsed answers, defaulting to a clean read for anyone unnamed."""
    clean = {
        "can_do": "He prices things nobody has assayed.",
        "in_the_way": "Somebody checks every price he signs.",
        "expect_next": "He gets read by somebody who matters.",
        "undefined_words": [],
        "open_questions": [],
    }
    return {
        reader.reader_id: by_reader.get(reader.reader_id, clean)
        for reader in comprehension.READERS
    }


# --- what passes and what does not ---------------------------------------------------------


def test_four_readers_who_followed_every_word_pass_the_premise() -> None:
    """The whole bar, and it is one number: zero undefined words across all four."""
    screen = comprehension.ScreenResult.of(answers())
    assert screen.passed
    assert screen.conformed
    assert screen.undefined_total == 0
    assert screen.readers_confused == 0


def test_one_word_one_reader_could_not_follow_fails_the_premise() -> None:
    """Not a majority and not a mean. One reader, one word, and the premise is re-forged.

    The bar is set where it is because the failure it exists to catch is exactly this: *"'every
    wonder is alive, small and kept in a crock' — makes no sense"* was one operator reading one
    premise, and averaging it against three readers who shrugged would have passed it.
    """
    screen = comprehension.ScreenResult.of(
        answers(
            stranger={
                "can_do": "Something with prices.",
                "in_the_way": "Not clear.",
                "expect_next": "No idea.",
                "undefined_words": ["the assay"],
                "open_questions": [],
            }
        )
    )
    assert not screen.passed
    assert screen.readers_confused == 1
    assert screen.undefined_total == 1
    assert dict(screen.undefined_by_reader)["stranger"] == ("the assay",)
    assert dict(screen.undefined_by_reader)["climber"] == ()


def test_open_questions_alone_never_fail_a_screen() -> None:
    """A pitch that leaves questions it plans to answer is working, not broken.

    The research battery's measured correction, carried here with the schema it lives in: one
    counter could not separate a withheld hook from an unexplained word, and a human-written
    reference pitch drew five items that were all hooks.
    """
    hooked = {
        "can_do": "He prices what nobody has assayed.",
        "in_the_way": "The second check is not his.",
        "expect_next": "I want to know who checks him.",
        "undefined_words": [],
        "open_questions": ["who is the second check", "what happens when a price is wrong"],
    }
    screen = comprehension.ScreenResult.of(
        answers(climber=hooked, stranger=hooked, regular=hooked, mechanism=hooked)
    )
    assert screen.passed
    assert screen.undefined_total == 0
    assert sum(len(quoted) for _, quoted in screen.open_questions_by_reader) == 8


def test_a_reader_whose_answer_cannot_be_read_fails_the_attempt() -> None:
    """Silence is not a pass, and this is the direction the check has to fail in.

    A screen that called a run clean because three readers answered and the fourth returned
    nothing would pass a premise on the strength of a provider error. Absent, `None`, and a
    shape the schema does not describe are all the same thing here: nobody said there were no
    undefined words.
    """
    for broken in (
        None,
        {"can_do": "x", "in_the_way": "y", "expect_next": "z"},
        {"undefined_words": "none", "open_questions": []},
    ):
        screen = comprehension.ScreenResult.of(answers(mechanism=broken))
        assert not screen.conformed
        assert not screen.passed
        assert screen.undefined_total == 0, "an unreadable answer is not a confusion"

    missing = comprehension.ScreenResult.of({"climber": answers()["climber"]})
    assert not missing.conformed
    assert not missing.passed


def test_a_non_string_in_the_quoted_list_is_not_counted_as_a_word() -> None:
    """`parse_schema_payload` checks required keys and top-level types, not item types.

    So a reader answering `undefined_words: [1, 2]` arrives here as a conforming answer, and
    the count has to be taken over something. Coerced and stripped: an empty string is not a
    quoted word, and neither is whitespace.
    """
    screen = comprehension.ScreenResult.of(
        answers(
            regular={
                "can_do": "x",
                "in_the_way": "y",
                "expect_next": "z",
                "undefined_words": ["", "   ", "the tide"],
                "open_questions": [],
            }
        )
    )
    assert dict(screen.undefined_by_reader)["regular"] == ("the tide",)
    assert screen.undefined_total == 1


def test_the_screen_block_round_trips_through_json() -> None:
    """The block lands in `forge.json`, so it has to survive being written and read back."""
    screen = comprehension.ScreenResult.of(
        answers(
            climber={
                "can_do": "x",
                "in_the_way": "y",
                "expect_next": "z",
                "undefined_words": ["the assay"],
                "open_questions": ["who checks him"],
            }
        )
    )
    block = json.loads(json.dumps(screen.to_jsonable(), ensure_ascii=False))
    assert block["passed"] is False
    assert block["conformed"] is True
    assert block["readers"] == [reader.reader_id for reader in comprehension.READERS]
    assert block["undefined_by_reader"]["climber"] == ["the assay"]
    assert block["open_questions_by_reader"]["climber"] == ["who checks him"]
    assert block["undefined_total"] == 1
    assert block["readers_confused"] == 1
    # The answers themselves are carried, because a count says a premise failed and the words
    # say what a reader could not follow. Neither ever reaches a prompt (§97.1).
    assert block["answers"]["climber"]["can_do"] == "x"


# --- what a reader is asked, and what they are not told ------------------------------------


def test_a_reader_request_carries_the_reader_the_premise_and_the_schema() -> None:
    reader = comprehension.READERS[0]
    request = comprehension.render_reader_request(reader, PREMISE)
    assert request.system == reader.system()
    assert reader.reads_for in request.system
    assert reader.drops_on in request.system
    assert request.prompt.startswith(PREMISE)
    assert "back-cover copy" in request.prompt
    assert request.schema == comprehension.ANSWER_SCHEMA
    assert request.profile == comprehension.SCREEN_PROFILE
    assert request.call_class == "generation"


def test_a_reader_is_never_given_the_house_rules() -> None:
    """A reader is not writing prose, and the rules for writing it would be contamination.

    `judge_panel.judge_request` is the existing precedent for a deliberately house-rule-free
    system on a role that reads rather than writes. This is the same boundary: the screen
    exists to check whether the house rules landed, and a screen carrying them is an instrument
    holding a copy of the answer.
    """
    for reader in comprehension.READERS:
        system = comprehension.render_reader_request(reader, PREMISE).system or ""
        assert house.HOUSE_RULES not in system
        assert "Clarity is the floor" not in system


def test_a_reader_is_given_the_premise_and_nothing_else() -> None:
    """Boundary 6: exactly what a real reader would have at that point.

    Somebody reading a back cover has the back cover. No world record, no title, no forge
    context and no sibling premise reaches this call — the argument is the whole of the input.
    """
    request = comprehension.render_reader_request(comprehension.READERS[0], PREMISE)
    assert request.prompt.replace(PREMISE, "").strip().startswith("---")
    assert "assay_grade" not in request.prompt
    assert "The Long Weight" not in request.prompt


def test_the_readers_name_no_published_work() -> None:
    """§97.3: anchor text may enter measurement and may never enter a generation-side prompt.

    The research panel these four derive from carries named works with verdicts attached. This
    module runs inside `forge`, in the process that writes the premise, so it carries the roles
    without the titles — and `architect._BORROWED`, the rail that refuses a borrowed comparison
    in forge output, is the same boundary from the other side.
    """
    for reader in comprehension.READERS:
        assert not architect._BORROWED.findall(reader.system())
    from personas import GENRE_PANEL  # the research panel, imported only to compare

    named = {anchor.work for persona in GENRE_PANEL for anchor in persona.anchors}
    rendered = " ".join(reader.system() for reader in comprehension.READERS)
    assert named, "the research panel carries anchors; if it stopped, this test means nothing"
    for work in named:
        assert work not in rendered


def test_the_production_screen_and_the_research_battery_ask_the_same_question() -> None:
    """The copy is deliberate and this pins that it is still a copy rather than a drift.

    `research/quality-measurement/comprehension_battery.py` is the frozen measuring stick the
    clarity work's before and after are read off; this module is the production screen. They
    may diverge — a change to one is not a change to the other — but a divergence that nobody
    decided is what this catches. If this fails, one of the two was edited and the ledger
    should say which.
    """
    battery = pytest.importorskip("comprehension_battery")
    assert comprehension.ANSWER_SCHEMA == battery.ANSWER_SCHEMA
    # The ask is not a module constant over there — it is inline in `main`'s loop, split across
    # two source lines — so the comparison that can be made is against the file's own text.
    flat = " ".join(Path(battery.__file__).read_text(encoding="utf-8").split())
    assert "That is the back-cover copy of a book you just picked up." in flat
    assert "do not quote the text back." in flat
    assert comprehension._ASK.startswith("That is the back-cover copy of a book you just")
    assert comprehension._ASK.endswith("do not quote the text back.")


# --- the gate, wired into the forge ---------------------------------------------------------


def registry_of(provider: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    import litharness.cli as cli_module
    from litharness.providers.registry import ProviderRegistry

    monkeypatch.setattr(
        cli_module, "build_default_registry", lambda *a, **k: ProviderRegistry(provider)
    )


def two_worlds() -> str:
    return json.dumps(
        {
            "worlds": [
                world(),
                world(title="Slack Water", domain="river ferry rights", geometry="cycle"),
            ]
        }
    )


def forged_at(out: Path) -> dict[str, Any]:
    return json.loads((out / "forge.json").read_text(encoding="utf-8"))


def test_a_forge_screens_every_premise_and_says_so_in_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Boundary 5's wiring: every candidate comes out with a screen block beside its premise.

    And the call sequence is the assertion under it — one world call, then a premise call and
    four reader calls per candidate. A forge that quietly skipped the screen would still write
    a file; it would not make eleven calls.

    Every reader here leaves a question the book is expected to answer, and every premise still
    passes: that is the half of the screen that reports and never gates, running through the
    whole command rather than only through `ScreenResult`.
    """
    from litharness.providers.fake import FakeProvider

    provider = FakeProvider()
    script = [two_worlds()]
    for _ in range(2):
        script.append(PREMISE)
        script.extend(
            reader_answer(questions=["who checks the checker"])
            for _ in comprehension.READERS
        )
    provider.set_responses(script)
    registry_of(provider, monkeypatch)

    out = tmp_path / "forge"
    database = tmp_path / "screen.db"
    assert main(["--database", str(database), "init"]) == 0
    assert main(
        [
            "--database", str(database), "forge", "a brief", "--k", "2",
            "--out", str(out), "--scenes", "8",
        ]
    ) == 0

    assert provider.calls == 1 + 2 * (1 + len(comprehension.READERS))
    assert provider.responses == []
    forged = forged_at(out)
    assert forged["usable"] == 2
    for bundle in forged["candidates"]:
        assert bundle["screen"]["passed"] is True
        assert bundle["screen"]["undefined_total"] == 0
        # Four readers, four questions, and the premise passed anyway.
        assert sum(
            len(quoted) for quoted in bundle["screen"]["open_questions_by_reader"].values()
        ) == len(comprehension.READERS)
        assert bundle["premise"] == PREMISE
        assert bundle["premise_complaints"] == []
        # The premise reached the bundle from the premise call, and the world it came from
        # carries none of its own.
        assert "premise" not in bundle["world"]
    assert forged["screen_spend"]["profile"] == comprehension.SCREEN_PROFILE
    assert forged["premise_spend"]["profile"] == architect.PREMISE_PROFILE


def test_a_premise_the_readers_could_not_follow_is_re_forged_once_and_then_marked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One fresh regeneration, one re-screen, and no third attempt.

    The regeneration is the identical ask asked again: nothing a reader quoted enters the
    prompt (§97.1), so what makes the second attempt different is the model and not the brief.
    Here the second attempt is scripted clean, which is what a regeneration is for.
    """
    from litharness.providers.fake import FakeProvider

    provider = FakeProvider()
    script = [two_worlds()]
    # Candidate one: a premise four readers stumble on, then a regeneration they follow.
    script.append(PREMISE)
    script.extend(reader_answer(undefined=["the tide"]) for _ in comprehension.READERS)
    script.append(PREMISE)
    script.extend(reader_answer() for _ in comprehension.READERS)
    # Candidate two: clean first time.
    script.append(PREMISE)
    script.extend(reader_answer() for _ in comprehension.READERS)
    provider.set_responses(script)
    registry_of(provider, monkeypatch)

    out = tmp_path / "forge"
    database = tmp_path / "screen.db"
    assert main(["--database", str(database), "init"]) == 0
    assert main(
        [
            "--database", str(database), "forge", "a brief", "--k", "2",
            "--out", str(out), "--scenes", "8",
        ]
    ) == 0
    assert provider.responses == []
    forged = forged_at(out)
    assert [bundle["screen"]["passed"] for bundle in forged["candidates"]] == [True, True]
    assert forged["usable"] == 2


def test_a_premise_that_fails_twice_is_carried_marked_and_refused_at_the_pick(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The refusal end to end: marked in the file, uncounted in `usable`, refused by `--pick`.

    A failed premise is re-forged rather than hand-patched, so the pick has to refuse it —
    otherwise the escape hatch boundary 5 forbids is an operator editing `directives.json`.
    """
    from litharness.providers.fake import FakeProvider

    provider = FakeProvider()
    script = [two_worlds()]
    for _ in range(2):  # two attempts for candidate one, both stumbled on
        script.append(PREMISE)
        script.extend(
            reader_answer(undefined=["the tide", "second seal"])
            for _ in comprehension.READERS
        )
    script.append(PREMISE)
    script.extend(reader_answer() for _ in comprehension.READERS)
    provider.set_responses(script)
    registry_of(provider, monkeypatch)

    out = tmp_path / "forge"
    database = tmp_path / "screen.db"
    assert main(["--database", str(database), "init"]) == 0
    assert main(
        [
            "--database", str(database), "forge", "a brief", "--k", "2",
            "--out", str(out), "--scenes", "8",
        ]
    ) == 0
    assert provider.responses == []

    forged = forged_at(out)
    failed, passed = forged["candidates"]
    assert failed["screen"]["passed"] is False
    assert failed["screen"]["undefined_total"] == 8
    assert failed["screen"]["readers_confused"] == len(comprehension.READERS)
    assert passed["screen"]["passed"] is True
    # A world clear of every gate whose premise nobody could follow is not usable.
    assert failed["report"]["gate_complaints"] == []
    assert forged["usable"] == 1

    assert main(
        ["--database", str(database), "forge", "--out", str(out), "--pick", "1"]
    ) == 2
    assert not (out / "seed.json").exists()
    # And the one that passed picks exactly as it always did.
    assert main(
        ["--database", str(database), "forge", "--out", str(out), "--pick", "2"]
    ) == 0
    assert (out / "seed.json").exists()


def test_a_premise_call_that_never_names_the_person_is_refused_before_any_reader_is_paid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`premise_complaints` runs first, and its one retry is its own.

    Four reader calls for a paragraph that is already deterministically wrong is money spent to
    learn what arithmetic already said, so the premise stage retries once and stops. Two calls
    for candidate one, and not a reader among them.
    """
    from litharness.providers.fake import FakeProvider

    provider = FakeProvider()
    nameless = "A city discovers what its ledger has really been counting."
    script = [two_worlds(), nameless, nameless, PREMISE]
    script.extend(reader_answer() for _ in comprehension.READERS)
    provider.set_responses(script)
    registry_of(provider, monkeypatch)

    out = tmp_path / "forge"
    database = tmp_path / "screen.db"
    assert main(["--database", str(database), "init"]) == 0
    assert main(
        [
            "--database", str(database), "forge", "a brief", "--k", "2",
            "--out", str(out), "--scenes", "8",
        ]
    ) == 0
    assert provider.responses == []

    forged = forged_at(out)
    failed, passed = forged["candidates"]
    assert any("never names" in item for item in failed["premise_complaints"])
    assert failed["screen"]["passed"] is False
    assert "never names" in failed["screen"]["reason"]
    assert "undefined_total" not in failed["screen"], "no reader was asked"
    assert passed["screen"]["passed"] is True
    assert forged["usable"] == 1


def test_a_bundle_forged_before_the_gate_existed_picks_exactly_as_it_did(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Absence keeps old behaviour, which is this repository's standing pattern.

    Six `forge.json` files sit in the tree with no screen key and every one of them was picked
    from before the gate existed. A bare subscript in the pick branch would park all of them
    over a fault none of them can be shown to have.
    """
    from litharness.providers.fake import FakeProvider

    provider = FakeProvider()
    provider.set_responses(forge_script(two_worlds(), premises=(PREMISE, PREMISE)))
    registry_of(provider, monkeypatch)

    out = tmp_path / "forge"
    database = tmp_path / "screen.db"
    assert main(["--database", str(database), "init"]) == 0
    assert main(
        [
            "--database", str(database), "forge", "a brief", "--k", "2",
            "--out", str(out), "--scenes", "8",
        ]
    ) == 0

    path = out / "forge.json"
    forged = json.loads(path.read_text(encoding="utf-8"))
    for bundle in forged["candidates"]:
        bundle.pop("screen")
    path.write_text(json.dumps(forged, ensure_ascii=False), encoding="utf-8")
    assert main(
        ["--database", str(database), "forge", "--out", str(out), "--pick", "1"]
    ) == 0
    assert (out / "seed.json").exists()


def test_no_flag_skips_the_screen() -> None:
    """*"A `--no-screen` escape hatch does not exist."* Asserted rather than remembered.

    The flag would be the whole of boundary 5 undone in one line, so its absence is a test
    rather than a note: `forge` refuses to parse one, which is what "does not exist" means to
    anybody typing it.
    """
    from litharness.cli import build_parser

    parser = build_parser()
    for flag in ("--no-screen", "--skip-screen", "--unscreened", "--screen"):
        with pytest.raises(SystemExit):
            parser.parse_args(["forge", "a brief", flag])
