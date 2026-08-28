"""The Recruiter's containment, and the arm it was built to make measurable.

`plan/handoff-writer-recruiter.md`. A Recruiter is **generative and upstream** — it proposes a
writer before any prose exists — so it needs containment rather than a validity licence, which
is `plan/director-role.md`'s argument for the Director applied one role over. Containment here
is four things, and each is a test below rather than a sentence in a docstring: an enumerated
tool allowance that cannot name the admission verb, a prompt that carries no craft doctrine of
its own, no dossier of its own, and no path anywhere on this route that could rank two writers.

**And the shapes are a registered arm, so their invariants are pinned before any call is paid
for.** The prediction, recorded in `plan/stage-0-decisions.md` §146 before the first draw:
`several-no-beat` locks lower than `several-with-beat`. If the assignment drifts after that is
written down, the arm is no longer the arm that was registered — which is what these tests are
for.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

import pytest

from litharness.application import recruiter, roster
from litharness.domain import house
from litharness.domain import writers as writers_domain
from litharness.domain.directors import prose_axes_named

SHAPES = sorted(writers_domain.DOSSIER_SHAPES)


def _system(shape: str) -> str:
    return recruiter.render_recruit_request("cozy-fantasy", shape=shape).system or ""


# ------------------------------------------------------------------------- the allowance


def test_the_recruiter_allowance_cannot_reach_roster_accept() -> None:
    """**Enumerated rather than wildcarded, and the Architect is why.**

    When this shipped, `world_agent.ALLOWED_TOOLS` was the single glob
    `Bash(litharness world:*)`, and `world accept` is itself a `litharness world ...` command —
    so on that point the Architect's containment rested on the last line of its tool essay
    rather than on its allowance. §146.9 measured that discrepancy real (the glob ran `world
    accept` on `claude` 2.1.236) and the Architect's allowance is enumerated now too. Four
    strings is the whole cost of never having repeated it here. No entry contains a comma,
    which matters because the CLI transport joins the allowance with one.
    """
    assert "accept" not in " ".join(recruiter.ALLOWED_TOOLS)
    assert not any("," in entry for entry in recruiter.ALLOWED_TOOLS)
    assert not any(
        entry == "Bash(litharness roster:*)" for entry in recruiter.ALLOWED_TOOLS
    )
    for shape in SHAPES:
        assert recruiter.render_recruit_request(
            "cozy-fantasy", shape=shape
        ).allowed_tools == recruiter.ALLOWED_TOOLS


def test_every_allowed_command_is_a_view_the_roster_actually_has() -> None:
    """An allowance naming a command that does not exist is an agent's first wasted turn."""
    named = {
        entry.removeprefix("Bash(litharness roster ").split(":")[0].rstrip(")")
        for entry in recruiter.ALLOWED_TOOLS
    }
    assert named == {"vocabulary", "show", "check", "declare"}
    # The two read views are named bare and the two that need flags are not. A wider string can
    # only ever permit more, so this asymmetry costs nothing whichever way the matcher goes.
    assert "Bash(litharness roster show)" in recruiter.ALLOWED_TOOLS
    assert "Bash(litharness roster declare:*)" in recruiter.ALLOWED_TOOLS


# ------------------------------------------------------------------------------ the prompt


@pytest.mark.parametrize("shape", SHAPES)
def test_the_recruit_prompt_contains_no_em_dash(shape: str) -> None:
    """The prompt tells the model a dossier with the mark in it never becomes a writer. A
    prompt that used the mark while saying so would be demonstrating the opposite, and §83's
    finding is that demonstration moves register where description does not."""
    assert "—" not in _system(shape)


def test_a_dossier_whose_only_offence_is_the_mark_is_refused_and_the_prompt_says_so() -> None:
    """The one claim in this prompt that is a factual assertion about the system, pinned so it
    fails loudly if `_CRAFT_INSTRUCTION` ever stops matching the character itself."""
    clean = (
        "You write cozy fantasy. What you love is competence at low volume, nothing more. "
        "You want a reader to close a chapter feeling like they could stay."
    )
    writers_domain.legal_dossier(clean)
    with pytest.raises(writers_domain.IllegalDossier):
        writers_domain.legal_dossier(clean.replace("volume,", "volume —"))
    assert "No dashes in it." in _system("single-image")


@pytest.mark.parametrize("shape", SHAPES)
def test_the_recruit_prompt_names_no_prose_axis_but_the_one_it_prohibits(shape: str) -> None:
    """`em_dash` matches on the word *punctuation*, and the precedent is exact and already
    argued: the listing role's own rule text says this market's listings *punctuate* with full
    stops and commas. The guard runs on dossiers and briefs, never on a task string, and a
    prompt that forbids craft talk has to name what craft talk is."""
    assert prose_axes_named(_system(shape)) == ("em_dash",)


@pytest.mark.parametrize("shape", SHAPES)
def test_the_recruiter_prompt_carries_no_craft_doctrine_of_its_own(shape: str) -> None:
    """**The house floor is absent for R1's reason rather than by oversight.**
    `tests/test_architecture.py` gives the criterion for the deliberately-absent list — a role
    producing reader-facing prose belongs on it — and this role's output is a bio nobody reads
    that is rendered into the system message of every scene call. §138 measured a rule's
    affirmative half coming back as a verbal formula in the output, and a Recruiter told *"every
    sentence can be followed the first time it is read"* is one paraphrase from writing that
    into a dossier, where `prose_axes_named` cannot see it."""
    system = _system(shape)
    for block in (house.CLARITY, house.READER, house.ACCUMULATION):
        assert block not in system
    source = Path(recruiter.__file__).read_text(encoding="utf-8")
    assert "with_house_rules(" not in source
    assert "system_for(" not in source


@pytest.mark.parametrize("shape", SHAPES)
def test_the_recruiter_prompt_is_a_tool_essay_and_would_pass_the_leak_rail_anyway(
    shape: str,
) -> None:
    """A tool essay is exempt from the machinery-word rail, the way the Architect's is: the
    boundary is what the text shapes, not where it lives. Measured rather than assumed, because
    an exemption nobody checks is an exemption that grows."""
    lowered = _system(shape).lower()
    assert not [word for word in house.MACHINERY_WORDS if word in lowered]


@pytest.mark.parametrize("shape", SHAPES)
def test_the_recruit_prompt_asks_what_this_person_reads_and_never_what_they_did_for_a_living(
    shape: str,
) -> None:
    """The G3 failure, which `writers.py`'s own CAST comment records: four career dossiers, four
    books set inside their authors' day jobs, four worlds with no magic in them. The prompt
    quotes that as a *result* and never as a rule, which is `house`'s standing constraint — a
    rule may say what fails and may not enumerate what succeeds."""
    system = _system(shape).lower()
    assert "it is an appetite and never a job they held" in system
    assert "four worlds with no magic in any of them" in system
    for word in ("trained", "profession", "apprentic", "years of", "worked as"):
        assert word not in system, word
    # **"career" appears exactly once and only as the thing that went wrong.** A prompt that
    # asked for one, or that used the word twice and lost track of which sense it meant, is the
    # drift this pins: the sentence has to stay a report of a result.
    assert system.count("career") == 1
    assert "four writers were once given careers instead" in system


@pytest.mark.parametrize("shape", SHAPES)
def test_the_recruit_prompt_names_no_demographic_field(shape: str) -> None:
    """Deep in domain, shallow in demography: a persona described demographically elicits
    stereotype performance, a model writing what it thinks that person sounds like."""
    system = _system(shape).lower()
    for word in (r"\bage\b", r"\baged\b", r"hometown", r"commute", r"grew up", r"years old"):
        assert not re.search(word, system), word


def test_the_shelf_reaches_the_prompt_half_and_never_the_system_half() -> None:
    """§136 measured the two words *progression fantasy* outweighing every rule in the prompt
    when a shelf label arrived as what a book is about; and a standing system instruction would
    give one shelf authority over every recruit this process makes."""
    request = recruiter.render_recruit_request("chinese-cultivation", shape="single-image")
    assert "Chinese Cultivation (in English)" in request.prompt
    assert "Chinese Cultivation" not in (request.system or "")
    assert "chinese-cultivation" not in request.prompt


def test_the_shelf_reaches_the_model_as_the_operators_own_words() -> None:
    """The label is character-for-character theirs; normalising it is an edit to their words."""
    assert roster.SPECIALIZATIONS["chinese-cultivation"] == "Chinese Cultivation (in English)"
    assert roster.SPECIALIZATIONS["litrpg-comedy"] == "LitRPG Comedy"


def test_the_prompt_asks_for_no_summary_of_its_own_work() -> None:
    """Unlike the Architect's seed, which closes on *"say what you built"*. A seeded world is
    hundreds of records no single command reads back; a dossier is eighty words `roster show`
    returns verbatim, so a prose summary would be the agent's opinion of its own output and the
    log has no containment for that."""
    system = _system("single-image").lower()
    assert "two or three sentences" not in system


def test_the_recruiter_wears_no_dossier_of_its_own() -> None:
    """A cast writer drafting a colleague's dossier is the premise lock at one remove."""
    assert "writer" not in inspect.signature(recruiter.render_recruit_request).parameters
    for shape in SHAPES:
        system = _system(shape)
        for writer in writers_domain.CAST.values():
            assert writer.render() not in system


# -------------------------------------------------------------------------- the registered arm


def test_the_slate_is_verbatim_the_operators_twelve() -> None:
    """A normalising edit is what this refuses. The slate is a recruitment brief rather than a
    quota, and both "varied" and "useful" are the operator's words.

    **Extended 2026-08-28, in the operator's words again**: after reviewing all twelve
    applications they said *"we are lacking some mystery, detective and historical
    specializations"* — so the roster admits two new shelves as SUPPLEMENTARY hires while the
    arm's slate stays exactly the original twelve. The first assertion pins the twelve
    verbatim; the second pins that the arm never silently absorbs a supplementary shelf."""
    operators_twelve = [
        "Light Fantasy",
        "Cozy Fantasy",
        "LitRPG Comedy",
        "Sci-Fi",
        "Dark Fantasy",
        "Supernatural",
        "Cultivation",
        "Chinese Cultivation (in English)",
        "Historical",
        "Progression Fantasy",
        "Isekai",
        "Portal Fantasy",
    ]
    assert list(roster.SPECIALIZATIONS.values())[:12] == operators_twelve
    assert [slug for slug, _ in recruiter.SLATE] == list(roster.SPECIALIZATIONS)[:12]
    assert list(roster.SPECIALIZATIONS.values())[12:] == ["Mystery", "Detective"]
    assert [slug for slug, _ in recruiter.SUPPLEMENTARY] == list(roster.SPECIALIZATIONS)[12:]
    arm_slugs = {slug for slug, _ in recruiter.SLATE}
    assert not arm_slugs & {slug for slug, _ in recruiter.SUPPLEMENTARY}


def test_supplementary_shelves_resolve_a_shape_and_stay_out_of_the_cells() -> None:
    """`shape_for` answers for a supplementary shelf (the twelve-shelf error message is gone
    for them), and the shape is the recorded production default, not a cell assignment."""
    assert recruiter.shape_for("mystery") == "several-no-beat"
    assert recruiter.shape_for("detective") == "several-no-beat"


def test_the_slate_puts_four_shelves_in_each_of_the_three_cells() -> None:
    counts: dict[str, int] = {}
    for _, shape in recruiter.SLATE:
        counts[shape] = counts.get(shape, 0) + 1
    assert counts == {
        "single-image": 4,
        "several-with-beat": 4,
        "several-no-beat": 4,
    }


def test_each_near_pair_is_split_across_the_contrast_with_the_direction_alternating() -> None:
    """**The partial within-shelf design, and it is a design rather than an accident.**

    On these three pairs the shelf is approximately held while the form varies, which is the
    only place in the slate where a difference can be read as the form's. Alternating the
    direction by pair index keeps which member goes first from being a factor of its own.

    Two of the three fell out of plain positional cycling and the third did not; three of three
    fall out of the stated rule. The difference is entirely whether it was written down first,
    which is the whole of why pre-registration is not paperwork.
    """
    assignment = dict(recruiter.SLATE)
    directions = []
    for anchor, neighbour in recruiter.NEAR_PAIRS:
        pair = {assignment[anchor], assignment[neighbour]}
        assert pair == {"several-with-beat", "several-no-beat"}, (anchor, neighbour)
        directions.append(assignment[anchor])
    assert directions == ["several-with-beat", "several-no-beat", "several-with-beat"]


def test_the_control_cell_holds_the_one_light_shelf_that_the_near_pairs_left_free() -> None:
    """Reproducing the shipped form on four more threat-forward shelves reproduces a result
    already on disk. LitRPG Comedy in the control is the one cell that asks the capability
    question the operator actually raised: does the shipped form force a dark opening on a shelf
    that should not have one?"""
    assert recruiter.shape_for("litrpg-comedy") == "single-image"


def test_the_three_shapes_render_three_prompts_and_three_profiles() -> None:
    """The arm is real: a shape that did not change the bytes would be a cell in name only."""
    systems = {shape: _system(shape) for shape in SHAPES}
    assert len(set(systems.values())) == 3
    profiles = {
        recruiter.render_recruit_request("cozy-fantasy", shape=shape).profile
        for shape in SHAPES
    }
    assert len(profiles) == 3


def test_the_contrast_cells_differ_only_in_whether_a_love_is_an_opening_beat() -> None:
    """The single factor the registered prediction is about. `single-image` differs from both in
    *two* things — one love, and a beat — which is why it is labelled the control and is not an
    arm of the contrast."""
    with_beat = _system("several-with-beat")
    no_beat = _system("several-no-beat")
    assert "three or four separate loves" in with_beat
    assert "three or four separate loves" in no_beat
    assert "phrase one of them as a moment a story opens on" in with_beat
    assert "none of them a moment a story opens on" in no_beat


def test_the_slate_is_what_recruit_uses_when_no_form_is_typed() -> None:
    """**The registered assignment is the default, and that is what stops it being mistyped.**
    `--shape` was `required=True` with no default and the only pointer to the slate was a help
    string, so an operator running the twelve had to look each one up and a slip filed a recruit
    into the wrong cell of a pre-registered arm — recorded on the row and in the decision profile
    as though it were the assignment, with nothing comparing the two.
    """
    from litharness.cli import build_parser

    parsed = build_parser().parse_args(["recruit", "--specialization", "isekai"])
    assert parsed.shape is None
    assert recruiter.shape_for("isekai") == "several-with-beat"
    for slug, shape in recruiter.SLATE:
        assert recruiter.shape_for(slug) == shape


def test_an_unknown_shelf_or_shape_is_refused_rather_than_silently_defaulted() -> None:
    with pytest.raises(ValueError):
        recruiter.render_recruit_request("grimdark", shape="single-image")
    with pytest.raises(ValueError):
        recruiter.render_recruit_request("cozy-fantasy", shape="whatever")
    with pytest.raises(ValueError):
        recruiter.shape_for("grimdark")


# ------------------------------------------------------------------------------- what is refused

#: Names that would mean this route had acquired a way to prefer one writer over another.
_RANKING = (
    "select_winner",
    "win_rate",
    "PairVerdict",
    "judge_panel",
    "distinctness",
    "DistinctnessReading",
    "rank",
    "score",
    "prefer",
    "best",
    "compare",
)


@pytest.mark.parametrize("module", (recruiter, roster))
def test_no_module_on_the_recruiter_path_can_rank_or_select_a_writer(module) -> None:
    """§61(5), §105.1, §107.5: no model ranks or selects among candidates unless the log's
    containment for it exists, and there is none for "which of these writers is better". The
    check is over the parsed source rather than the text, so a word inside a docstring
    explaining the refusal does not trip it."""
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
    } | {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
    }
    assert not names & set(_RANKING), sorted(names & set(_RANKING))


def test_the_recruiter_records_no_cast_event_and_mints_no_column_for_one() -> None:
    """"Least-recently-cast" has no substrate: **nothing anywhere records which writer drafted
    which book**, so a `last_cast_at` column would be a field nothing writes — which is
    `target_words`' defect, already paid for twice in this repository."""
    migration = (
        Path(__file__).parents[1] / "migrations" / "035_writer_roster.sql"
    ).read_text(encoding="utf-8")
    for column in ("cast_at", "last_cast", "cast_count", "rank ", "score ", "preference"):
        assert column not in migration, column


def test_no_shelf_label_the_recruiter_holds_can_reach_a_book_brief() -> None:
    """A shelf is a store column and a prompt input. §136 is what a shelf label does when it
    arrives as a brief, and the roster suite has no flag that could carry one."""
    for module in (recruiter, roster):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "import overview" not in source
        assert "render_overview_request" not in source


def test_the_exemplar_socket_is_not_reachable_from_the_recruiter_path() -> None:
    """Socket only, own-generated if ever admitted, and admission sits on R1's boundary as an
    operator act rather than a build decision."""
    from litharness.adapters.sqlite_roster import SqliteRosterRepository

    parameters = inspect.signature(
        SqliteRosterRepository.record_proposed_writer
    ).parameters
    assert "exemplar_digest" not in parameters
    assert "--exemplar" not in Path(
        Path(recruiter.__file__).parents[2] / "litharness" / "cli.py"
    ).read_text(encoding="utf-8")
