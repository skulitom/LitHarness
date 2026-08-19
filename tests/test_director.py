"""The Director role: a personality that says what a book is, and never whether it is good.

**What these tests do not establish.** Nothing here shows a director produces a better book, or
that any two of them differ in a way a reader would notice. The first is a reader question and
waits with every other reader question; the second costs §61's confidence level divided by the
director count, which `plan/director-role.md` §4 prices before anybody spends it.

What they establish is containment — that the role cannot do the things a role which measures
nothing must not be able to do. The tests worth reading are the refusals: a brief that instructs
about prose, a director issuing a veto, a machine-authored directive minting a locked plan item,
and two directors that turn out to be one director in hats.
"""

from __future__ import annotations

import ast
from pathlib import Path

import litharness_contracts as lc
import pytest

from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.directive_planner import is_verbatim_actionable
from litharness.application.director import (
    DIRECT_PRIORITY,
    DIRECTIVE_EVERY,
    DirectorOutputError,
    direct_job_id,
    directive_from,
    render_request,
    scene_block,
)
from litharness.application.narrative_planner import proposal_from_model
from litharness.cli import EXIT_FAULT, EXIT_OK, main
from litharness.domain import directors as directors_mod
from litharness.domain.directives import (
    INTERPRETIVE_KINDS,
    VERBATIM_KINDS,
    Directive,
    DirectiveKind,
    directive_id_for,
)
from litharness.domain.directors import (
    BUILTIN,
    DIRECTOR_KINDS,
    Distinctness,
    IllegalBrief,
    build,
    distinctness,
    is_machine_author,
    machine_author,
)
from litharness.domain.generation import CompletionResult
from tests.conftest import BOOK_ID, BRANCH_ID, make_revision

STAMP = "2026-08-19T00:00:00Z"
DELVER = BUILTIN["delver"]


def a_result(**payload: object) -> CompletionResult:
    return CompletionResult(
        text="{}", provider="stub", model="stub-v1", parsed=dict(payload),
        schema_requested=True,
    )


# -- the brief guard, and the reuse that had to be withdrawn -------------------------------


def test_a_brief_may_not_instruct_about_prose() -> None:
    """A brief goes straight into the drafting context, so one that named a prose axis would
    inject it with no counter, no E6 validation and no reader — the axis-admission path
    bypassed by a role that was never asked to respect it."""
    for doctrine in (
        "Write with short sentences and avoid em dashes.",
        "Keep the status block vague.",
        "Show, don't tell.",
        "Cut the adverbs.",
        "Vary the punctuation.",
    ):
        with pytest.raises(IllegalBrief, match="what the book is about"):
            build("x", doctrine)


def test_the_guard_does_not_refuse_ordinary_genre_direction() -> None:
    """**The regression that produced the guard's second version.** Its first reused the
    Judge's frozen `AXIS_MATCHERS`, which are "deliberately generous about vocabulary and strict
    about topic" because E6 asks whether an axis reached the output at all — so `stat_flatten`'s
    list contains `level`, `tier`, `stat`, `value` and `count`, which are ordinary LitRPG *story*
    words. It rejected this project's own first example brief.

    Same list, opposite error economics: in E6 a generous list costs a false positive that reads
    as a miss; as a refusal gate it costs a refusal of legitimate direction."""
    for story in (
        "Every level gained should cost something the reader watched being spent.",
        "The System is a creditor before it is a game; keep the stats of the debt visible.",
        "More dungeon crawling, fewer council scenes.",
        "Let time pass, and let one choice change a whole season.",
    ):
        build("y", story)  # must not raise
    for director in BUILTIN.values():
        build(director.name, director.brief)


def test_a_director_is_addressed_by_its_own_words() -> None:
    """A brief cannot drift under the books it directed: editing one word mints a different
    director, which is what keeps "which director wrote this book" answerable afterwards."""
    one = build("a", "Push the book toward descent and cost.")
    two = build("a", "Push the book toward descent and costs.")
    assert one.director_id != two.director_id
    assert build("a", one.brief).director_id == one.director_id
    with pytest.raises(IllegalBrief, match="does not address"):
        directors_mod.Director(
            director_id="dtor-wrong", name="a", brief=one.brief
        )


# -- the licence: which kinds, and which authority -----------------------------------------


def test_a_director_may_emit_exactly_the_interpretive_kinds() -> None:
    """`CONSTRAINT` and `VETO` are `VERBATIM_KINDS` — preserve the words, lock them — and a veto
    is a *refusal*, which is authority rather than direction. `CONTROL` is pause/resume/kill."""
    assert frozenset(INTERPRETIVE_KINDS) == DIRECTOR_KINDS
    assert not DIRECTOR_KINDS & VERBATIM_KINDS
    assert DirectiveKind.CONTROL not in DIRECTOR_KINDS


def test_a_director_that_issues_a_veto_is_refused() -> None:
    for kind in (DirectiveKind.VETO, DirectiveKind.CONSTRAINT, DirectiveKind.CONTROL):
        with pytest.raises(DirectorOutputError, match="may not emit"):
            directive_from(
                a_result(kind=kind.value, body="no more mazes"),
                DELVER, book_id=BOOK_ID, branch_id=BRANCH_ID, at=STAMP,
            )


def test_a_director_that_instructs_about_prose_is_refused_at_the_directive_too() -> None:
    """The brief is checked at construction and every directive is checked again: a legal brief
    does not license an illegal instruction, and the model writes the second one."""
    with pytest.raises(DirectorOutputError, match="not legal"):
        directive_from(
            a_result(kind="tone_note", body="Trim the em dashes out of the prose."),
            DELVER, book_id=BOOK_ID, branch_id=BRANCH_ID, at=STAMP,
        )


def test_a_malformed_answer_is_a_failed_call_and_never_an_empty_directive() -> None:
    with pytest.raises(DirectorOutputError, match="schema"):
        directive_from(
            CompletionResult(text="", provider="s", model="s", schema_requested=True),
            DELVER, book_id=BOOK_ID, branch_id=BRANCH_ID, at=STAMP,
        )
    with pytest.raises(DirectorOutputError, match="non-empty body"):
        directive_from(
            a_result(kind="arc_note", body="   "),
            DELVER, book_id=BOOK_ID, branch_id=BRANCH_ID, at=STAMP,
        )


def test_a_directive_a_director_wrote_says_so() -> None:
    directive = directive_from(
        a_result(kind="arc_note", body="Take them under the road."),
        DELVER, book_id=BOOK_ID, branch_id=BRANCH_ID, at=STAMP,
    )
    assert directive.author == machine_author(DELVER.director_id)
    assert is_machine_author(directive.author)
    assert not is_machine_author(None) and not is_machine_author("")


# -- the prerequisite: the laundering path's third costume ---------------------------------


def test_the_author_is_in_the_id_so_a_machine_row_cannot_be_reattributed() -> None:
    """The same words from a person and from a Director are two directives with two ids, so an
    instruction cannot be quietly relabelled and a machine's cannot collapse onto a human's.

    And an author-less id is unchanged, because a migration that moved existing ids would break
    every `produced_constraint_ids` reference pointing at one."""
    human = directive_id_for(DirectiveKind.ARC_NOTE, "more crawling", STAMP)
    machine = directive_id_for(DirectiveKind.ARC_NOTE, "more crawling", STAMP, "director:x")
    assert human != machine
    assert directive_id_for(DirectiveKind.ARC_NOTE, "more crawling", STAMP, None) == human


def test_a_machine_authored_directive_is_never_verbatim_actionable() -> None:
    """The verbatim lane's whole product is a `locked=True` constraint that then sits in every
    subsequent context packet as the director's word. The lock is the *human* director's
    authority and a personality has none to spend."""
    words = {
        "kind": DirectiveKind.CONSTRAINT,
        "body": "The toll is never waived.",
        "book_id": BOOK_ID,
        "branch_id": BRANCH_ID,
    }
    human = Directive(directive_id="dir-h", **words)
    machine = Directive(
        directive_id="dir-m", author=machine_author(DELVER.director_id), **words
    )
    assert is_verbatim_actionable(human)
    assert not is_verbatim_actionable(machine)


def test_a_machine_authored_directive_cannot_mint_a_locked_plan_item(
    tmp_path,
) -> None:
    """The interpretive lane's half of the same fix. The model sets `locked` on every edit it
    proposes, so a Director's direction could otherwise arrive wearing a person's standing —
    downgraded rather than refused, because the direction is legitimate and only its authority
    is not."""
    store = SqliteStore.open(tmp_path / "director.db")
    try:
        store.commit_revision(make_revision(), created_at=STAMP)
        store.record_plan_items(
            BOOK_ID,
            BRANCH_ID,
            [
                lc.PlanItem(
                    logical_id="plan-premise",
                    kind=lc.PlanKind.PREMISE,
                    text="A debtor works off an impossible debt.",
                    authority=lc.PlanAuthority.INTENDED,
                )
            ],
            created_at=STAMP,
        )
        base = store.plan_revision(BOOK_ID, BRANCH_ID)
        assert base is not None
        payload = {
            "summary": "s",
            "rationale": "r",
            "expected_outcome": "e",
            "interpretation": "i",
            "edits": [
                {
                    "action": "create",
                    "logical_id": "arc-descent",
                    "kind": "constraint",
                    "authority": "intended",
                    "text": "The road goes down.",
                    "locked": True,
                    "reason": "director",
                }
            ],
        }
        result = CompletionResult(text="", provider="s", model="s")
        machine = Directive(
            directive_id="dir-m",
            kind=DirectiveKind.ARC_NOTE,
            body="Take them under the road.",
            book_id=BOOK_ID,
            branch_id=BRANCH_ID,
            author=machine_author(DELVER.director_id),
        )
        proposal = proposal_from_model(
            payload, base=base, directive=machine, result=result
        )
        [edit] = proposal.edits
        assert edit.item is not None and edit.item.locked is False, (
            "a machine's direction may not wear the human director's authority"
        )
        assert proposal.readings[0].produced_constraint_ids == (), (
            "and it produces no locked constraint to cite"
        )

        human = Directive(
            directive_id="dir-h",
            kind=DirectiveKind.ARC_NOTE,
            body="Take them under the road.",
            book_id=BOOK_ID,
            branch_id=BRANCH_ID,
        )
        [human_edit] = proposal_from_model(
            payload, base=base, directive=human, result=result
        ).edits
        assert human_edit.item is not None and human_edit.item.locked is True, (
            "a person's directive still locks, which is what the downgrade is protecting"
        )
    finally:
        store.close()


# -- the Director never sees the prose -----------------------------------------------------


def test_the_director_is_handed_the_books_shape_and_never_its_prose() -> None:
    """A role that cannot see the text cannot render a verdict on it, so "may not evaluate
    prose" is a property of what it was handed rather than an instruction it might drift from.
    Summaries say what happened; prose says how it reads, and only the second is the dead
    frame."""
    prose = "Rook counted the coins twice and said nothing at all about the toll."
    request = render_request(
        DELVER,
        premise="A debtor works off a debt.",
        statements=[("scene-1", "Rook counts the toll")],
        summaries={"scene-1": "Rook counts what he owes."},
        drafted=1,
        of_total=6,
        open_promises=["the toll is never explained"],
    )
    blob = f"{request.system}\n{request.prompt}"
    assert prose not in blob
    assert "Rook counts what he owes." in blob, "summaries are structural and are shown"
    assert DELVER.brief in request.system
    assert "do not instruct about" in request.prompt


def test_the_director_store_cannot_write_prose() -> None:
    """Structural, over the protocol rather than the call sites: `DirectorStore` has no
    `commit_revision`, so the role could not write a scene even if something asked it to."""
    from litharness.application.ports import DirectorStore

    assert not hasattr(DirectorStore, "commit_revision")
    assert hasattr(DirectorStore, "scene_summaries")


# -- bounding ------------------------------------------------------------------------------


def test_direction_is_bounded_by_accepted_scenes_rather_than_plan_churn() -> None:
    """One directive per block of accepted scenes. The obvious alternative — one per plan epoch
    — is a spin loop wearing a bound, because a directive becomes a plan application and a plan
    application bumps the epoch."""
    revision = make_revision()
    assert scene_block(None) == 0
    assert scene_block(revision) == len(
        [n for n in revision.nodes if n.content]
    ) // DIRECTIVE_EVERY
    first = direct_job_id(BOOK_ID, BRANCH_ID, 0)
    assert first == direct_job_id(BOOK_ID, BRANCH_ID, 0), "replay converges"
    assert first != direct_job_id(BOOK_ID, BRANCH_ID, 1)


def test_a_director_never_outranks_a_person() -> None:
    """Both human lanes mint at 1000+ and 500+. A machine that could bury a person's direction
    would be the opposite of what the direction inbox is for."""
    assert DIRECT_PRIORITY < 500
    assert DIRECT_PRIORITY > 0, "and still ahead of the drafting it shapes"


# -- distinctness: is this two directors, or one in hats? ----------------------------------


def test_byte_identical_directors_read_identical() -> None:
    """§89.1 in a third costume: `qwen3:14b` returned one distinct answer vector across four
    personas, byte-identical, and a panel that read as four judges was one judge replicated. A
    graded distance would have reported that as a small number rather than as the categorical
    failure it was, which is why identity is checked first."""
    same = ["take them down", "take them lower", "take them deeper"]
    assert distinctness(same, list(same)).reading is Distinctness.IDENTICAL


def test_too_few_draws_is_unreadable_rather_than_passing() -> None:
    reading = distinctness(["a", "b"], ["c", "d"])
    assert reading.reading is Distinctness.UNREADABLE
    assert not reading.comparable


def test_directors_that_differ_more_than_they_wobble_read_distinct() -> None:
    left = [
        "Take the party under the road and make them pay for the light.",
        "Take the party under the road and make them pay for the rope.",
        "Take the party under the road and make them pay for the maps.",
    ]
    right = [
        "Bring the creditor to the door and let the debt be spoken aloud.",
        "Bring the creditor to the door and let the favour be called in.",
        "Bring the creditor to the door and let the contract be read out.",
    ]
    reading = distinctness(left, right)
    assert reading.reading is Distinctness.DISTINCT, reading
    assert reading.between is not None and reading.within is not None
    assert reading.between > reading.within
    assert reading.comparable


def test_a_deterministic_generator_reads_no_floor_rather_than_distinct() -> None:
    """**A control that cannot fail is not a control** (§50). When every draw from a director
    comes back byte-identical to its siblings — which a temperature-0 model always does, and the
    padded fake always does — the within-director noise floor is zero, and "between exceeds
    within" is then satisfied by a single differing character. It still establishes that the
    briefs are not inert; it does not establish a margin, and the two must not share a word."""
    reading = distinctness(["a", "a", "a"], ["bbbb", "bbbb", "bbbb"])
    assert reading.reading is Distinctness.DISTINCT_NO_FLOOR
    assert reading.within == 0.0
    assert reading.comparable, "not inert is still the thing the rail is checking for"


def test_a_comparison_between_indistinct_directors_is_not_comparable() -> None:
    """The rail: a director comparison may not be reported until the directors read DISTINCT,
    because anything else is comparing one director against itself and reporting the seed."""
    wobbly = [
        "Take them under the road tonight and make it cost.",
        "Bring the creditor to the door and let it cost.",
        "Let the season turn and make it cost.",
    ]
    near = [
        "Take them under the road tonight and make it cost.",
        "Bring the creditor to the door and let it cost.",
        "Let the season turn and make it cost, slowly.",
    ]
    reading = distinctness(wobbly, near)
    assert reading.reading is not Distinctness.DISTINCT
    assert not reading.comparable


# -- nothing here can block ----------------------------------------------------------------


def test_no_module_on_the_director_path_can_construct_a_gate() -> None:
    """I3 from `plan/reader-judge-loop.md`, extended to the third role. A Director cannot set
    `blocking`, build a gate, or park a unit — enforced by the absence of the capability rather
    than the absence of a caller.

    `application/director.py` is exempt from the import half and not the construction half: it
    is a job handler, and `conductor` requires handlers to be able to *fail* a unit. What it may
    not do is refuse one on quality."""
    root = Path(__file__).parents[1]
    source = (root / "src/litharness/domain/directors.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert not names & {"GateOutcome", "PolicyDecision"}
    handler = (root / "src/litharness/application/director.py").read_text(encoding="utf-8")
    assert "GateOutcome" not in handler and "blocking" not in handler


# -- the operator surface -------------------------------------------------------------------


def test_admitting_a_personality_is_an_operator_act(tmp_path, capsys) -> None:
    db = tmp_path / "cli.db"
    assert main(["--database", str(db), "init"]) == EXIT_OK
    capsys.readouterr()
    assert main(["--database", str(db), "directors"]) == EXIT_OK
    assert "no director admitted" in capsys.readouterr().out

    assert main(["--database", str(db), "directors", "--register", "delver"]) == EXIT_OK
    out = capsys.readouterr().out
    assert DELVER.director_id in out and "admitted" in out

    assert main(["--database", str(db), "directors", "--register", "delver"]) == EXIT_OK
    assert "already admitted" in capsys.readouterr().out


def test_an_illegal_brief_is_refused_at_the_command_line(tmp_path, capsys) -> None:
    db = tmp_path / "cli.db"
    main(["--database", str(db), "init"])
    capsys.readouterr()
    assert main([
        "--database", str(db), "directors", "--register", "sloppy",
        "--brief", "Keep the sentences short and drop the em dashes.",
    ]) == EXIT_FAULT
    assert "what the book is about" in capsys.readouterr().err


def test_an_unregistered_director_is_refused_rather_than_ignored(tmp_path) -> None:
    """A typo that silently produced the control arm would be the worst possible failure for an
    experiment whose whole question is whether the arms differ."""
    db = tmp_path / "cli.db"
    main(["--database", str(db), "init"])
    with pytest.raises(SystemExit, match="no director"):
        main(["--database", str(db), "--director", "nobody", "tick"])


def test_the_directive_listing_says_who_wrote_each_line(tmp_path, capsys) -> None:
    """A machine-authored directive that looked exactly like a person's on the operator surface
    would be the listing half of the laundering path the author column closed."""
    db = tmp_path / "cli.db"
    main(["--database", str(db), "init"])
    store = SqliteStore.open(db)
    try:
        store.submit_directive(
            Directive(
                directive_id="dir-machine",
                kind=DirectiveKind.ARC_NOTE,
                body="Take them under the road.",
                author=machine_author(DELVER.director_id),
            ),
            received_at=STAMP,
        )
        store.submit_directive(
            Directive(
                directive_id="dir-person",
                kind=DirectiveKind.ARC_NOTE,
                body="More dungeon crawling.",
            ),
            received_at=STAMP,
        )
    finally:
        store.close()
    capsys.readouterr()
    assert main(["--database", str(db), "directives"]) == EXIT_OK
    out = capsys.readouterr().out
    assert machine_author(DELVER.director_id) in out
    assert "human" in out
    assert "1 written by a director" in out
