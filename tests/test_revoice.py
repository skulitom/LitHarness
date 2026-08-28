"""The two revoicing calls, and the five gates on what the second one returns.

`plan/dossier-voice-direction.md`. The properties here fail silently in the way this subsystem's
always do — by rendering a prompt, by minting an id, or by writing a row — and four of them are
containment rather than correctness:

1. **The descriptor reaches exactly one call.** It is a prose-craft statement by construction, so
   what makes it legal is where it is allowed to land: the draw, never the rewrite, never a
   dossier. One import of it into the wrong prompt and the axis rides every scene call.
2. **Neither call carries the house floor.** `recruiter`'s recorded reason, one step earlier: a
   passage nobody reads becomes the paragraph that rides every scene call.
3. **Neither call carries a tool allowance.** Not an enumerated one — none.
4. **A rewrite is refused rather than redrawn.** Selection among candidates by preference is the
   rail §61(5) and §105.1 hold, and there is no code path here that could take a second draw.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

from litharness.application import revoice
from litharness.domain import house, voice, writers
from litharness.domain.writers import IllegalDossier

DESCRIPTOR = voice.StyleDescriptor(
    sentence_words_mean=11.5,
    sentence_words_sd=6.0,
    sentence_words_p10=3.0,
    sentence_words_p50=10.0,
    sentence_words_p90=21.0,
    paragraph_sentences_mean=2.5,
    connective_density=5.25,
    person=voice.Person.THIRD,
    tense=voice.Tense.PAST,
)

WRITER = writers.CAST["ferreira"]

#: A passage with nothing in common with any dossier on disk, so a shared run in a test is a
#: shared run the code produced rather than one the fixtures share by accident.
PASSAGE = (
    "The lift stopped between floors. Dust came down. Somebody two decks up was shouting a "
    "number over and over, and the number kept going up."
)


# ------------------------------------------------------------------ where the descriptor lands


def test_the_draw_cannot_be_made_without_a_descriptor() -> None:
    """An unaimed draw is our own register coming back in a costume, so it is unrepresentable.

    Structural rather than discouraged: `descriptor` is keyword-only with no default, so a
    caller that forgot it gets a `TypeError` at the call rather than a passage nobody can say
    what aimed.
    """
    parameter = inspect.signature(revoice.render_exemplar_request).parameters["descriptor"]
    assert parameter.default is inspect.Parameter.empty
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY


def test_the_descriptor_reaches_the_draw_and_only_the_draw() -> None:
    """The containment claim of the whole design, as two assertions.

    Sentence length and connective density are what `directors._PROSE_STYLE` refuses in a brief.
    They are legal here because they aim one call and are two steps from the paragraph that
    repeats: the draw sees them, the passage carries whatever survived, and the rewrite sees the
    passage.
    """
    draw = revoice.render_exemplar_request(WRITER, descriptor=DESCRIPTOR)
    assert "connective_density" in draw.prompt
    assert "sentence_words_mean" in draw.prompt

    rewrite = revoice.render_rewrite_request(dossier=WRITER.dossier, exemplar=PASSAGE)
    whole = f"{rewrite.system or ''}\n{rewrite.prompt}"
    # The rendered pairs rather than the bare field names: `person` is also an ordinary English
    # word and the rewrite prompt says *"a paragraph by the same person"*, so a bare-name check
    # fails on prose that carries no descriptor at all.
    assert revoice.render_descriptor(DESCRIPTOR) not in whole
    for name, value in DESCRIPTOR.as_labels().items():
        assert f"{name} {value}" not in whole, name
    assert DESCRIPTOR.descriptor_id not in whole


def test_the_descriptor_arrives_in_the_prompt_half() -> None:
    """§136's rule inherited: per-draw material goes in the prompt, never in the system message.

    Two words under a system heading outweighed every rule in the prompt once already. A standing
    system instruction would also give one draw's aim authority over every draw this process
    makes, which is the shape `recruiter.render_recruit_request` refuses for the shelf label.
    """
    draw = revoice.render_exemplar_request(WRITER, descriptor=DESCRIPTOR)
    assert "connective_density" not in (draw.system or "")


def test_the_descriptor_block_says_it_is_not_a_standard() -> None:
    """Without the closing clause the block reads as a bar, and a model handed one reports it."""
    rendered = revoice.render_descriptor(DESCRIPTOR)
    assert "not a judgment" in rendered
    assert "says what good prose is" in rendered


# ------------------------------------------------------------------------- what the calls carry


def test_neither_call_carries_the_house_floor() -> None:
    """`recruiter`'s recorded reason, one step earlier in the same chain.

    A passage nobody reads becomes the paragraph that rides the system message of every scene
    call the writer ever makes. The floor is also constant across every writer, so it contributes
    nothing to the differentiation an exhibited voice exists to create while contributing §138's
    failure — a rule's affirmative half coming back as a verbal formula — at the worst leverage
    available in this system.
    """
    draw = revoice.render_exemplar_request(WRITER, descriptor=DESCRIPTOR)
    rewrite = revoice.render_rewrite_request(dossier=WRITER.dossier, exemplar=PASSAGE)
    for request in (draw, rewrite):
        assert house.HOUSE_RULES not in (request.system or "")
        assert house.CLARITY not in (request.system or "")
        assert house.READER not in (request.system or "")


def test_neither_call_carries_a_tool_allowance() -> None:
    """Not an enumerated allowance: none. Both return text a caller writes down itself.

    The matcher question `recruiter.ALLOWED_TOOLS` had to reason around — whether
    `Bash(prefix:*)` is a prefix match — cannot arise for a call that passes nothing.
    """
    draw = revoice.render_exemplar_request(WRITER, descriptor=DESCRIPTOR)
    rewrite = revoice.render_rewrite_request(dossier=WRITER.dossier, exemplar=PASSAGE)
    assert draw.allowed_tools == ()
    assert rewrite.allowed_tools == ()


def test_the_draw_wears_the_writers_dossier_and_the_rewrite_wears_nobody() -> None:
    """A writer draws as itself; a rewriter is nobody.

    A cast writer rewriting a colleague's dossier is the premise lock at one remove, which is
    `recruiter`'s recorded reason for `writer=None`. A writer rewriting *its own* dossier is
    worse: a role editing its own containment surface.
    """
    draw = revoice.render_exemplar_request(WRITER, descriptor=DESCRIPTOR)
    assert WRITER.dossier.strip() in (draw.system or "")

    rewrite = revoice.render_rewrite_request(dossier=WRITER.dossier, exemplar=PASSAGE)
    for name in writers.CAST:
        assert name not in (rewrite.system or "")
    assert WRITER.dossier.strip() not in (rewrite.system or "")


def test_the_paragraph_is_the_last_thing_in_the_rewrite_prompt() -> None:
    """`system_for`'s order argument one level down: a model acts on the last thing it is given,
    and what it acts on is the paragraph. The passage is what it acts with."""
    rewrite = revoice.render_rewrite_request(dossier=WRITER.dossier, exemplar=PASSAGE)
    assert rewrite.prompt.index(PASSAGE) < rewrite.prompt.index(WRITER.dossier.strip())
    assert rewrite.prompt.rstrip().endswith(WRITER.dossier.strip())


def test_the_two_acts_are_separable_on_a_decision_row() -> None:
    """One frozen profile per act, so spend is attributable without a join back to the roster."""
    draw = revoice.render_exemplar_request(WRITER, descriptor=DESCRIPTOR)
    rewrite = revoice.render_rewrite_request(dossier=WRITER.dossier, exemplar=PASSAGE)
    assert draw.profile == revoice.EXEMPLAR_PROFILE != rewrite.profile == revoice.REWRITE_PROFILE


def test_a_rewrite_needs_something_to_rewrite_and_something_to_rewrite_against() -> None:
    with pytest.raises(IllegalDossier):
        revoice.render_rewrite_request(dossier="  ", exemplar=PASSAGE)
    with pytest.raises(IllegalDossier):
        revoice.render_rewrite_request(dossier=WRITER.dossier, exemplar="  ")


# ------------------------------------------------------------------------------- the five gates


def _accept(returned: str, *, original: str = "You write about tides and what they take.") -> str:
    return revoice.accept_rewrite(original=original, exemplar=PASSAGE, returned=returned)


def test_a_preamble_is_caught_by_the_one_paragraph_rule() -> None:
    """The cheap catch for a model that answered instead of returning, and it is honest about
    what it misses: a one-line preamble survives, and what backstops that is the proposal landing
    unaccepted in front of a person."""
    with pytest.raises(IllegalDossier, match="more than one paragraph"):
        _accept("Here is the rewrite:\n\nYou write about the sea and what it keeps.")


def test_an_empty_rewrite_is_refused() -> None:
    with pytest.raises(IllegalDossier):
        _accept("   ")


def test_r1_still_refuses_a_rewrite_that_names_an_axis() -> None:
    """Unchanged and unweakened: a rewrite that started explaining its own register never mints."""
    with pytest.raises(IllegalDossier):
        _accept("You write about the sea. Your sentence length is your own business.")


def test_the_census_refuses_a_rewrite_that_carries_a_mark() -> None:
    """**The gate the direction note asks for by name.**

    A dossier may no more demonstrate a measured axis than name one. An em-dash-laden exhibited
    voice asserts by example the thing the em-dash loop exists to test, and `prose_axes_named`
    was catching this case only because the character sits inside its naming pattern.
    """
    with pytest.raises(IllegalDossier, match="registered prose axis"):
        _accept("You write about the sea — and what it keeps.")


def test_the_borrowing_control_refuses_a_lifted_clause() -> None:
    """§85's distinction, made a refusal: a model shown prose moves toward it by feature or by
    phrase, and after the fact the two are not separable."""
    lifted = (
        "You write the kind of thing where somebody two decks up was shouting a number over "
        "and over, and you love it."
    )
    with pytest.raises(IllegalDossier, match="borrowing rather than register"):
        _accept(lifted)


def test_a_rewrite_that_changed_nothing_is_refused() -> None:
    """It would mint a second writer whose dossier differs from its parent's in nothing that ever
    reaches a prompt, because the exemplar digest is addressed material and the dossier is not."""
    original = "You write about tides and what they take."
    with pytest.raises(IllegalDossier, match="unchanged"):
        _accept(original, original=original)


def test_a_clean_rewrite_comes_back_stripped() -> None:
    accepted = _accept("  You write the sea. You write what it keeps.  ")
    assert accepted == "You write the sea. You write what it keeps."


# ------------------------------------------------------------------------------------- the rail


def test_the_revoice_module_names_no_ranking_symbol() -> None:
    """Nothing here ranks, scores, prefers, or takes a second draw.

    Checked over the parsed AST rather than the source text, so the docstrings that explain *why*
    there is no redraw are safe while a function or attribute that did it is not. This mirrors the
    roster suite's own rail, which is where the shape comes from.
    """
    tree = ast.parse(Path(revoice.__file__).read_text(encoding="utf-8"))
    named: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            named.add(node.name)
        elif isinstance(node, ast.Name):
            named.add(node.id)
        elif isinstance(node, ast.Attribute):
            named.add(node.attr)
    for forbidden in ("rank", "ranked", "score", "scored", "prefer", "best", "retry", "redraw"):
        assert not any(forbidden in name.lower() for name in named), forbidden
