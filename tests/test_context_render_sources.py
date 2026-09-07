"""Exact packet rendering provenance, without substring matching or prompt changes."""

from __future__ import annotations

import litharness_contracts as lc
import pytest

from litharness.domain import context as ctx


def item(item_id: str, text: str) -> ctx.PackedItem:
    return ctx.PackedItem(
        item_id=item_id,
        kind=lc.ContextItemKind.FACT,
        source_logical_id=f"source:{item_id}",
        source_kind=lc.ResourceKind.UNKNOWN,
        text=text,
        tokens=ctx.count_tokens(text),
        authority=lc.StateAuthority.AUTHOR_LOCKED,
        pov_visibility=("observer",),
        span=(10, 10 + len(text)),
    )


def packet(sections: dict[str, tuple[ctx.PackedItem, ...]], **kwargs) -> ctx.ContextPacket:
    return ctx.ContextPacket(
        query_id="query",
        target_logical_id="scene",
        book_id="book",
        branch_id="branch",
        base_revision_id="revision",
        sections=sections,
        **kwargs,
    )


# Fixed pre-source-map renderings. These pin the public text contract independently of
# the new span composition; whitespace, labels and section order all affect writer input.
BLOCKS = {
    ctx.PREMISE: "Premise: premise body",
    ctx.CONSTRAINTS: (
        "Locked constraints and promises — these are the director's and may not "
        "be contradicted:\n- constraints body"
    ),
    ctx.INTENTIONS: (
        "Planned story — intentions, not events that have already happened. "
        "Established prose and author locks take precedence. Later events and "
        "reveals belong at their planned positions; the current scene plan "
        "determines what happens now:\nintentions body"
    ),
    ctx.RULES: (
        "World rules and limits — established facts, subject to author locks; "
        "their presence here does not mean a character knows them. "
        "Scene plans, milestones and dramatic instructions must fit these facts. "
        "Apply each rule within its stated scope and declared exceptions. "
        "Satisfy a cost, prerequisite or activation condition before its dependent effect, "
        "unless the rule explicitly allows delayed payment. Preserve declared quantities "
        "and entity identities across actions and scenes. These constrain what happens; "
        "they are not a checklist of explanations to put in the prose:\n- rules body"
    ),
    ctx.THREADS: "Open threads the book still owes:\n- threads body",
    ctx.CAST: "Who is in this story:\ncast body",
    ctx.FACTS: (
        "Established facts (POV: observer) — world truth, not automatically character "
        "knowledge:\n- facts body"
    ),
    ctx.HIDDEN: (
        "True, and the reader has not been told — write as if it is true and never "
        "put it on the page. Nothing here may be explained, hinted at as a summary, "
        "or spoken by a character who does not know it; the scene must simply stay "
        "consistent with it:\n- hidden body"
    ),
    ctx.HISTORY: (
        "Earlier states — these were true then and have since been replaced; use "
        "them only as history, never as the current state:\n- history body"
    ),
    ctx.SUMMARIES: (
        "Earlier scenes, in summary — these happened and are established; write the "
        "new scene in full dramatised prose, never in this register:\n- summaries: summaries body"
    ),
    ctx.PRIOR_PROSE: "The story so far, in full:\n\n[item:prior_prose]\nprior_prose body",
}


@pytest.mark.parametrize("include_constraints", [False, True])
@pytest.mark.parametrize("include_rules", [False, True])
def test_all_sections_keep_exact_rendering_and_attribute_original_items(
    include_constraints, include_rules
):
    sections = {
        section: (item(f"item:{section}", f"{section} body"),)
        for section in reversed(tuple(BLOCKS))
    }
    p = packet(sections, pov_character_id="observer")
    expected_sections = [
        section
        for section in BLOCKS
        if not (section == ctx.CONSTRAINTS and not include_constraints)
        and not (section == ctx.RULES and not include_rules)
    ]
    expected = "\n\n".join(BLOCKS[section] for section in expected_sections)
    rendered = p.render_with_sources(
        include_constraints=include_constraints, include_rules=include_rules
    )
    assert rendered.text == expected
    assert (
        p.render(include_constraints=include_constraints, include_rules=include_rules) == expected
    )
    assert [span.section for span in rendered.spans] == expected_sections
    for span in rendered.spans:
        original = sections[span.section][0]
        assert span.item is original
        assert rendered.text[span.start : span.end] == original.text
        assert span.start == expected.index(original.text, expected.index(BLOCKS[span.section]))
        assert span.item.source_logical_id == f"source:item:{span.section}"
        assert span.item.authority is lc.StateAuthority.AUTHOR_LOCKED
        assert span.item.pov_visibility == ("observer",)
        # Existing quoted-source coordinates are retained, not replaced by rendered offsets.
        assert span.item.span == (10, 10 + len(original.text))
    assert (
        p.render_constraints_with_sources().text
        == p.render_constraints()
        == BLOCKS[ctx.CONSTRAINTS]
    )
    assert p.render_rules_with_sources().text == p.render_rules() == BLOCKS[ctx.RULES]


def test_duplicates_and_heading_text_are_attributed_to_insertions_not_first_match():
    heading = "Established facts — world truth, not automatically character knowledge:"
    first, second = item("first", heading), item("second", heading)
    p = packet({ctx.FACTS: (first, second)})
    rendered = p.render_with_sources()
    assert rendered.text == f"{heading}\n- {heading}\n- {heading}"
    first_start = len(heading) + 3
    second_start = first_start + len(heading) + 3
    assert rendered.spans == (
        ctx.RenderedItem(ctx.FACTS, first, first_start, first_start + len(heading)),
        ctx.RenderedItem(ctx.FACTS, second, second_start, second_start + len(heading)),
    )


@pytest.mark.parametrize("section", list(BLOCKS))
def test_multiline_unicode_and_empty_item_bodies_preserve_exact_offsets(section):
    items = (
        item("empty", ""),
        item("multiline", "Ω🙂\r\n\n- a line\nThe story so far, in full:\n"),
        item("duplicate", "Ω🙂\r\n\n- a line\nThe story so far, in full:\n"),
        item("last", ""),
    )
    rendered = packet({section: items}).render_with_sources()
    assert [span.item for span in rendered.spans] == list(items)
    assert [span.section for span in rendered.spans] == [section] * len(items)
    assert rendered.spans[0].start == rendered.spans[0].end
    assert rendered.spans[-1].start == rendered.spans[-1].end == len(rendered.text)
    for span in rendered.spans:
        assert rendered.text[span.start : span.end] == span.item.text
        assert span.end - span.start == len(span.item.text)
    for previous, following in zip(rendered.spans, rendered.spans[1:], strict=False):
        assert previous.end <= following.start
    assert rendered.spans[1].start < rendered.spans[2].start


def test_empty_sections_have_no_phantom_source_spans():
    p = packet(dict.fromkeys(BLOCKS, ()))
    empty = ctx.RenderedContext("", ())
    assert p.render_with_sources() == empty
    assert p.render_rules_with_sources() == empty
    assert p.render_constraints_with_sources() == empty
    assert p.render() == p.render_rules() == p.render_constraints() == ""


def test_item_free_syntax_stays_outside_source_spans():
    p = packet(
        {
            ctx.SUMMARIES: (item("summary:older", "remembered"),),
            ctx.PRIOR_PROSE: (item("scene:earlier", "happened"),),
        }
    )
    rendered = p.render_with_sources()
    summary, prose = rendered.spans
    assert rendered.text[summary.start : summary.end] == "remembered"
    assert rendered.text[prose.start : prose.end] == "happened"
    assert rendered.text[summary.start - len("- older: ") : summary.start] == "- older: "
    assert (
        rendered.text[prose.start - len("[scene:earlier]\n") : prose.start] == "[scene:earlier]\n"
    )
