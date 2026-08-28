"""The `roster` suite as an agent meets it: the four views, the two exit contracts, and refusal.

A separate file from `tests/test_cli.py` for the reason the world suite is exercised from
`tests/test_world_supersession.py`: that file is organised around the scheduler's interface and
is long, and a tool suite an agent holds is its own interface.

**What is being asserted here is mostly the interface rather than the storage.** The rails the
store holds are in `tests/test_writer_roster.py`; what these tests protect is the half that has
now been paid for three times in this repository — an agent that cannot learn a command's shape
from the command learns it by writing records. So: `vocabulary` names each field's *shape*, the
worked example it prints is parsed and guarded here so it cannot rot, `check --dossier` exits
zero whatever it finds, and `declare` refuses without leaving a row behind.
"""

from __future__ import annotations

import contextlib
import io
import json
import shlex

import pytest

from litharness.application import roster as roster_mod
from litharness.cli import EXIT_FAULT, EXIT_OK, build_parser, main
from litharness.domain import writers as writers_domain

LEGAL = (
    "You write the kind of fantasy where the stakes are a bakery, a bad harvest and "
    "somebody's estranged aunt. What you love is competence at low volume. You want a "
    "reader to close a chapter feeling like they could stay."
)
#: Its only offence is the mark itself. `_CRAFT_INSTRUCTION`'s `em_dash` pattern matches U+2014,
#: and that is not a false positive: a dossier rides in the system message of every scene call,
#: so one written with the mark demonstrates it on every draft.
EM_DASHED = LEGAL.replace("volume.", "volume — nothing more.")


@pytest.fixture
def db(tmp_path):
    return tmp_path / "roster.db"


def run(db, *args: str) -> int:
    return main(["--database", str(db), *args])


def payload(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


def declare(db, name: str = "okafor", *, dossier: str = LEGAL, **flags) -> int:
    argv = [
        "roster",
        "declare",
        name,
        "--dossier",
        dossier,
        "--specialization",
        flags.pop("specialization", "cozy-fantasy"),
        "--shape",
        flags.pop("shape", "several-no-beat"),
    ]
    for interest in flags.pop("interests", ("cozy fantasy", "small towns")):
        argv += ["--interest", interest]
    return run(db, *argv)


# ------------------------------------------------------------------------ the vocabulary


def test_the_vocabulary_names_every_field_shape_and_not_only_its_name(db, capsys) -> None:
    """`world.vocabulary` was written because nothing in `--help` said which of two words a
    predicate wanted, and its fix was a sentence per predicate. A sentence has nowhere to put
    "required" or "repeats", which is why that payload still does not say `precedes` needs its
    criterion in `--value`. Here each field is an object."""
    assert run(db, "roster", "vocabulary") == EXIT_OK
    fields = payload(capsys)["fields"]
    for name, field in fields.items():
        assert {"flag", "type", "repeats", "required", "constraints", "example"} <= set(
            field
        ), name
    assert fields["interest"]["repeats"] is True
    assert fields["dossier"]["repeats"] is False
    assert fields["dossier"]["required"] is True


def test_the_vocabulary_shows_one_assembled_declare_command_that_is_itself_legal() -> None:
    """An agent that has to compose a command out of five hint strings composes it wrong.

    The example is parsed with the real parser and its dossier run through the real guard, so
    it cannot rot into a command line the interface would refuse.
    """
    argv = shlex.split(roster_mod.EXAMPLE_DECLARE)
    assert argv[:3] == ["litharness", "roster", "declare"]
    parsed = build_parser().parse_args(argv[1:])
    writers_domain.legal_dossier(parsed.dossier)
    assert parsed.interests == ["cozy fantasy", "small towns and shopfronts"]


def test_the_vocabulary_names_the_mark_that_refused_four_of_the_first_ten_dossiers(
    db, capsys
) -> None:
    assert run(db, "roster", "vocabulary") == EXIT_OK
    hard = " ".join(payload(capsys)["refused"]["hard"])
    assert "—" in hard


def test_the_vocabulary_offers_no_field_a_demography_could_land_in(db, capsys) -> None:
    """Deep in domain, shallow in demography. A persona described demographically elicits
    stereotype performance, which is a different behaviour wearing the same words."""
    assert run(db, "roster", "vocabulary") == EXIT_OK
    assert set(payload(capsys)["fields"]) == {
        "name",
        "dossier",
        "interest",
        "specialization",
        "shape",
        "note",
    }


def test_the_shape_vocabulary_has_one_home() -> None:
    """The membership is the domain's and `application/roster.SHAPES` only maps it."""
    assert frozenset(roster_mod.SHAPES) == writers_domain.DOSSIER_SHAPES


# ----------------------------------------------------------------------------- rehearsal


def test_check_rehearses_a_candidate_without_landing_a_record_or_a_nonzero_exit(
    db, capsys
) -> None:
    """**The exit-zero assertion is the point.** A rehearsal that exits nonzero is a rehearsal
    an agent stops running, and an agent that stops rehearsing goes back to learning the
    interface by writing records. The verdict is in the payload, where a machine reads it.

    **`axes_named` was `["em_dash"]` here until 2026-08-28 and is now `[]`, and the assertion
    changed because the payload was wrong rather than because the rule did.** This dossier names
    nothing; it carries a mark. Both facts were being reported under the heading for the first
    one, because the bare character sat inside the *naming* pattern — which the roster vocabulary
    contradicted in as many words, explaining the em dash as a demonstration on every draft. The
    refusal is unchanged: same dossier, same `legal: False`, same exit code, said correctly.
    """
    assert run(db, "init") == EXIT_OK
    capsys.readouterr()
    assert run(db, "roster", "check", "--dossier", EM_DASHED) == EXIT_OK
    read = payload(capsys)
    assert read["legal"] is False
    assert read["axes_named"] == []
    assert read["axes_carried"] == ["em_dash"]
    assert read["has_em_dash"] is True

    assert run(db, "roster", "show") == EXIT_OK
    assert payload(capsys)["writers"] == []


def test_check_exits_nonzero_when_the_roster_itself_is_wrong(db, capsys) -> None:
    """The audit mode keeps `world check`'s contract, and only the audit mode does.

    `EXIT_FAULT` is 2, not 1. The help string said "exits 1" — copied from `world check`, which
    says the same and is also wrong — and an operator loop written to that contract would never
    fire on a broken roster while colliding with `EXIT_ATTENTION`, which `recruit` returns for a
    run that declared nobody. Fixed here; the world suite's copy is left for its own change.
    """
    assert run(db, "init") == EXIT_OK
    assert declare(db) == EXIT_OK
    capsys.readouterr()
    assert run(db, "roster", "check") == EXIT_OK

    from litharness.adapters.sqlite_store import SqliteStore

    with SqliteStore.open(db) as store:
        store._connection.execute(
            "UPDATE roster_writers SET dossier = ?", (LEGAL.replace("bakery", "brewery"),)
        )
    capsys.readouterr()
    assert run(db, "roster", "check") == EXIT_FAULT
    assert "does not address its own content" in " ".join(payload(capsys)["complaints"])


def test_the_check_census_reports_a_machinery_word_and_never_complains_about_one(
    db, capsys
) -> None:
    """`writers.BUILTIN["volcanology"]` contains *"the standing argument with people whose town
    it was"*, which is ordinary English. A counter that refuses a shipped fixture is a counter
    measuring the wrong thing, so this is a census and never a complaint."""
    assert run(db, "init") == EXIT_OK
    assert declare(db, dossier=LEGAL.replace("low volume", "low standing")) == EXIT_OK
    capsys.readouterr()
    assert run(db, "roster", "check") == EXIT_OK
    read = payload(capsys)
    assert read["ok"] is True
    (census,) = read["census"].values()
    assert census["machinery_words"] == ["standing"]


# ------------------------------------------------------------------------------- declare


def test_a_declared_writer_lands_proposed_and_cannot_draft_yet(db, capsys) -> None:
    assert run(db, "init") == EXIT_OK
    assert declare(db) == EXIT_OK
    capsys.readouterr()
    assert run(db, "roster", "show") == EXIT_OK
    (row,) = payload(capsys)["writers"]
    assert row["status"] == "proposed"
    assert row["specialization"] == "cozy-fantasy"
    assert row["shape"] == "several-no-beat"

    assert run(db, "listing", "--writer", "okafor") == EXIT_FAULT
    assert "roster accept okafor" in capsys.readouterr().err


def test_a_dossier_that_names_a_registered_prose_axis_is_refused_and_leaves_no_row(
    db, capsys
) -> None:
    """R1, at the first of its two runs. **The record-free half is the assertion that matters**:
    a refused dossier that left a row behind would be a poisoned record every later read raises
    on, which is not leniency."""
    assert run(db, "init") == EXIT_OK
    assert declare(db, dossier="You write with short punchy sentences.") == EXIT_FAULT
    err = capsys.readouterr().err
    assert "prose_style" in err
    assert "roster check --dossier" in err

    assert run(db, "roster", "show") == EXIT_OK
    assert payload(capsys)["writers"] == []


def test_a_dossier_carrying_an_em_dash_is_refused(db, capsys) -> None:
    assert run(db, "init") == EXIT_OK
    assert declare(db, dossier=EM_DASHED) == EXIT_FAULT
    assert "em_dash" in capsys.readouterr().err


def test_a_name_the_compiled_cast_already_holds_is_refused_at_declare(db, capsys) -> None:
    assert run(db, "init") == EXIT_OK
    assert declare(db, "ferreira") == EXIT_FAULT
    assert "compiled writer's name" in capsys.readouterr().err


def test_declare_refuses_a_shape_that_disagrees_with_the_run_it_is_inside(
    db, capsys, monkeypatch
) -> None:
    """What makes "one shelf per call" and "do not standardise on one form" mechanical rather
    than prose: a declaration contradicting the run's stamp would put a dossier in the wrong
    cell of a registered arm with nothing on the record saying so."""
    assert run(db, "init") == EXIT_OK
    monkeypatch.setenv("LITHARNESS_RECRUIT_SHAPE", "single-image")
    assert declare(db, shape="several-no-beat") == EXIT_FAULT
    err = capsys.readouterr().err
    assert "single-image" in err and "several-no-beat" in err


def test_a_shelf_that_came_from_the_environment_is_checked_like_one_that_came_from_a_flag(
    db, capsys, monkeypatch
) -> None:
    """A value taken from the environment has never met `argparse`'s `choices`.

    The form was refused in the adapter and the shelf was not, so a mistyped variable landed a
    row on a shelf that does not exist, `roster check` reported it from then on, and `declare`
    has no retraction to undo it with.
    """
    assert run(db, "init") == EXIT_OK
    monkeypatch.setenv("LITHARNESS_RECRUIT_SHELF", "not-a-shelf")
    monkeypatch.setenv("LITHARNESS_RECRUIT_SHAPE", "single-image")
    assert (
        run(db, "roster", "declare", "okafor", "--dossier", LEGAL) == EXIT_FAULT
    )
    assert "not one of the twelve shelves" in capsys.readouterr().err
    assert run(db, "roster", "check") == EXIT_OK


def test_a_declaration_with_no_shelf_or_form_is_refused_and_points_at_the_vocabulary(
    db, capsys
) -> None:
    assert run(db, "init") == EXIT_OK
    assert (
        run(db, "roster", "declare", "okafor", "--dossier", LEGAL, "--specialization",
            "cozy-fantasy")
        == EXIT_FAULT
    )
    assert "roster vocabulary" in capsys.readouterr().err


# -------------------------------------------------------------------------------- accept


def test_accepting_promotes_the_writer_and_writes_exactly_one_decision(db, capsys) -> None:
    from litharness.adapters.sqlite_store import SqliteStore

    assert run(db, "init") == EXIT_OK
    assert declare(db) == EXIT_OK
    with SqliteStore.open(db) as store:
        before = store._connection.execute(
            "SELECT COUNT(*) FROM policy_decisions"
        ).fetchone()[0]
    capsys.readouterr()

    assert run(db, "roster", "accept") == EXIT_OK
    assert "accepted 1 of 1" in capsys.readouterr().out

    with SqliteStore.open(db) as store:
        after = store._connection.execute(
            "SELECT COUNT(*) FROM policy_decisions"
        ).fetchone()[0]
        decision_id = store.roster_rows()[0]["decision_id"]
        gate = store.load_decision(decision_id).gates[0]
    assert after == before + 1
    assert gate.rule_or_critic_id == "roster.accept.v0"


def test_the_same_refusal_runs_again_at_accept_and_leaves_the_writer_where_it_was(
    db, capsys
) -> None:
    """R1's second run, and it is not a formality: `directors._CRAFT_INSTRUCTION` grows as the
    reader loop admits axes, so a dossier declared last month passed a smaller vocabulary than
    the one governing the prompt it is about to ride in.

    The row is written through the store rather than through `declare`, which is what standing
    in for that growth requires — `declare` refuses it, so nothing else could ever produce the
    row this check exists to catch, and the check would be vacuous.
    """
    from litharness.adapters.sqlite_store import SqliteStore

    assert run(db, "init") == EXIT_OK
    with SqliteStore.open(db) as store:
        legal = writers_domain.build("okafor", LEGAL, interests=("cozy fantasy",))
        store.record_proposed_writer(
            legal,
            specialization="cozy-fantasy",
            shape="several-no-beat",
            proposed_at="2026-08-28T00:00:00Z",
        )
        store._connection.execute(
            "UPDATE roster_writers SET dossier = ?, writer_id = ?",
            (
                EM_DASHED,
                writers_domain.writer_id_for(
                    name="okafor", dossier=EM_DASHED, interests=("cozy fantasy",)
                ),
            ),
        )
    capsys.readouterr()

    assert run(db, "roster", "accept") == EXIT_FAULT
    assert "left proposed" in capsys.readouterr().err
    with SqliteStore.open(db) as store:
        assert store.roster_rows()[0]["status"] == "proposed"


def test_accept_is_refused_while_a_recruit_run_is_in_flight(db, capsys, monkeypatch) -> None:
    """The lock that does not depend on how a `Bash(prefix:*)` rule is matched."""
    assert run(db, "init") == EXIT_OK
    assert declare(db) == EXIT_OK
    monkeypatch.setenv("LITHARNESS_RECRUIT_SHELF", "cozy-fantasy")
    capsys.readouterr()
    assert run(db, "roster", "accept") == EXIT_FAULT
    assert "acceptance is an operator act" in capsys.readouterr().err

    from litharness.adapters.sqlite_store import SqliteStore

    with SqliteStore.open(db) as store:
        assert store.roster_rows()[0]["status"] == "proposed"


def test_naming_a_writer_that_was_never_proposed_is_refused_rather_than_ignored(
    db, capsys
) -> None:
    assert run(db, "init") == EXIT_OK
    assert run(db, "roster", "accept", "nobody") == EXIT_FAULT
    assert "no proposed writer named nobody" in capsys.readouterr().err


def test_two_proposals_under_one_name_are_reported_and_the_rest_of_the_batch_still_lands(
    db, capsys
) -> None:
    """**The blocking defect this test was written for.** Two proposals under one name are legal
    and expected — an edited dossier is a different writer — and the partial index only forbids
    two *accepted* ones. The batch's own duplicate check looked at accepted rows and not at
    itself, so a bare `roster accept` reached the UPDATE loop and died on `UNIQUE constraint
    failed: roster_writers.name`, naming neither writer, moving nothing, and writing no decision.
    With no retraction in the suite, that made the documented operator path dead for that
    database forever.

    Two things had to change and both are asserted here: the collision is reported like any other
    refusal and the untouched writers still go through, and the pair stays acceptable one at a
    time by id.
    """
    assert run(db, "init") == EXIT_OK
    assert declare(db, "stroud") == EXIT_OK
    assert declare(db, "stroud", dossier=LEGAL.replace("bakery", "brewery")) == EXIT_OK
    assert declare(db, "vosburgh") == EXIT_OK
    capsys.readouterr()

    assert run(db, "roster", "accept") == EXIT_OK
    read = capsys.readouterr()
    assert "accepted 1 of 3" in read.out
    assert "vosburgh" in read.out
    assert "stroud" in read.err and "has to have one answer" in read.err

    assert run(db, "roster", "show", "--json") == EXIT_OK
    by_status = {
        (row["name"], row["writer_id"]): row["status"]
        for row in payload(capsys)["writers"]
    }
    contested = sorted(wid for (name, wid), status in by_status.items() if name == "stroud")
    assert all(by_status[("stroud", wid)] == "proposed" for wid in contested)

    assert run(db, "roster", "accept", contested[0]) == EXIT_OK
    assert "accepted 1 of 1" in capsys.readouterr().out


def test_a_refusal_this_system_writes_never_reaches_an_operator_as_a_traceback(
    db, capsys
) -> None:
    """`IllegalDossier` subclasses `IllegalBrief`, which is a bare `Exception`, so before it
    joined `main`'s handler a stored dossier that a later-registered prose axis had made illegal
    escaped `prompts --writer` as a stack trace and **exit 1** — the code reserved for "a unit
    needs a human" — while `roster check` reported the same row as a fault and exited 2. That is
    the exact failure shape `main`'s own comment records `sqlite3.Error` being added to fix.
    """
    from litharness.adapters.sqlite_store import SqliteStore

    assert run(db, "init") == EXIT_OK
    assert declare(db) == EXIT_OK
    assert run(db, "roster", "accept") == EXIT_OK
    with SqliteStore.open(db) as store:
        store._connection.execute(
            "UPDATE roster_writers SET dossier = ?",
            ("You write with short punchy sentences.",),
        )
    capsys.readouterr()

    assert run(db, "prompts", "--writer", "okafor") == EXIT_FAULT
    assert "prose_style" in capsys.readouterr().err


def test_every_roster_view_writes_utf8_rather_than_the_consoles_own_codec(db) -> None:
    """**This host's stdout codec is cp1252**, and two of these payloads break on it. `roster
    vocabulary` names the em dash as the character it refuses, which cp1252 turns into a byte no
    UTF-8 reader can parse; and a dossier for the shelf called *Chinese Cultivation (in English)*
    can hold characters cp1252 cannot encode at all, which kills `roster show` outright for every
    writer on the roster. `_say` exists for this and records the sixteen-minute `architect seed`
    run that died printing its own report.
    """

    class Buffered:
        def __init__(self) -> None:
            self.buffer = io.BytesIO()

        def flush(self) -> None:
            pass

    def read(*argv: str) -> dict:
        stream = Buffered()
        with contextlib.redirect_stdout(stream):  # type: ignore[arg-type]
            assert run(db, *argv) == EXIT_OK
        written = stream.buffer.getvalue()
        assert written, argv
        # Raises `UnicodeDecodeError` on a cp1252 em dash and `JSONDecodeError` on a truncated
        # payload, which are the two shapes the defect took.
        return json.loads(written.decode("utf-8"))

    assert run(db, "init") == EXIT_OK
    assert declare(db, "wen", interests=("dāntián lore", "sects")) == EXIT_OK
    assert "—" in " ".join(read("roster", "vocabulary")["refused"]["hard"])
    assert read("roster", "show")["writers"][0]["interests"] == ["dāntián lore", "sects"]
    assert read("roster", "check")["ok"] is True


# ----------------------------------------------------------------------------------- show


def test_show_hides_dossier_prose_until_it_is_asked_for(db, capsys) -> None:
    """Showing four one-paragraph exemplars in the same form to a model asked to write a fifth
    produces that form a fifth time, which would be the control smuggled into the arms."""
    assert run(db, "init") == EXIT_OK
    assert declare(db) == EXIT_OK
    capsys.readouterr()

    assert run(db, "roster", "show") == EXIT_OK
    read = payload(capsys)
    assert "dossier" not in read["writers"][0]
    assert all("dossier" not in entry for entry in read["cast"])

    assert run(db, "roster", "show", "--dossier") == EXIT_OK
    assert "estranged aunt" in payload(capsys)["writers"][0]["dossier"]


def test_show_never_returns_an_operator_note_to_whoever_is_holding_the_tools(
    db, capsys
) -> None:
    """An annotation is where a preference gets written down — *"this one came out too grim, the
    next should go lighter"* is exactly the sentence somebody would put there — and a view a
    generative agent holds is where that preference would reach another generative agent, with no
    decision row and nothing measured behind it. The vocabulary tells the agent no roster view
    returns it, and this is what makes that true."""
    assert run(db, "init") == EXIT_OK
    assert (
        run(
            db, "roster", "declare", "okafor", "--dossier", LEGAL,
            "--specialization", "cozy-fantasy", "--shape", "several-no-beat",
            "--note", "came out too grim, go lighter next time",
        )
        == EXIT_OK
    )
    capsys.readouterr()
    for argv in (["roster", "show"], ["roster", "show", "--dossier"]):
        assert run(db, *argv) == EXIT_OK
        printed = capsys.readouterr().out
        assert "too grim" not in printed, argv
        assert "note" not in json.loads(printed)["writers"][0], argv


def test_show_reports_which_of_the_twelve_shelves_have_nobody_on_them(db, capsys) -> None:
    assert run(db, "init") == EXIT_OK
    assert declare(db) == EXIT_OK
    capsys.readouterr()
    assert run(db, "roster", "show") == EXIT_OK
    read = payload(capsys)
    assert "cozy-fantasy" not in read["unstaffed"]
    assert set(read["unstaffed"]) == set(roster_mod.SPECIALIZATIONS) - {"cozy-fantasy"}


def test_the_roster_command_offers_no_view_that_orders_or_prefers(db) -> None:
    """Rail 4 read off the command surface itself: there is no view here that could rank.

    **`refuse` joined the surface in stage-0 §149 and does not weaken this.** The rail forbids
    a view that *orders* or *prefers* — anything that could say one dossier is better than
    another, or hand back a sorted candidate list. Refusal is a verdict on one writer against
    nothing, addressed by name or id and carrying a reason a person typed; it is `accept`'s
    twin, not a comparison. What would break this test is a view that ranked, scored, shortlisted
    or picked, and none of the six does.
    """
    parser = build_parser()
    (roster_action,) = [
        action
        for action in parser._subparsers._group_actions[0].choices["roster"]._actions
        if getattr(action, "choices", None) and "declare" in action.choices
    ]
    assert set(roster_action.choices) == {
        "vocabulary",
        "show",
        "check",
        "declare",
        "accept",
        "refuse",
    }


# ------------------------------------------------------------------------------ end to end


def test_an_accepted_recruit_drafts_a_prompt_without_a_code_change(db, capsys) -> None:
    """The whole point of the store half, asserted once: a writer that did not exist when this
    binary was built reaches a real drafting prompt, and the four compiled controls are
    untouched."""
    assert run(db, "init") == EXIT_OK
    assert declare(db) == EXIT_OK
    assert run(db, "roster", "accept") == EXIT_OK
    capsys.readouterr()

    assert run(db, "prompts", "--writer", "okafor", "--role", "listing", "--json") == EXIT_OK
    assert "estranged aunt" in payload(capsys)["system"]


def test_prompts_resolves_a_writer_without_creating_a_database(tmp_path, capsys) -> None:
    """`SqliteStore.open` creates and migrates the file, so an inspection command that resolved
    unconditionally would leave a database behind in whatever directory it was run from."""
    absent = tmp_path / "absent.db"
    assert main(["--database", str(absent), "prompts", "--json"]) == EXIT_OK
    assert not absent.exists()


def test_an_unknown_writer_name_exits_loudly_on_both_of_its_two_contracts(
    db, capsys
) -> None:
    """The two are deliberately different and would otherwise be refactored into one: the
    conductor inherits `_director_id`'s `SystemExit`, which escapes `main` as exit 1, while an
    operator command prints and returns `EXIT_FAULT`. Exit codes are the interface."""
    assert run(db, "init") == EXIT_OK
    assert run(db, "listing", "--writer", "nobody") == EXIT_FAULT
    assert "the cast is" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        run(db, "tick", "--writer", "nobody")
