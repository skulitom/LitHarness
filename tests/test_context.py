"""Context assembly (§12 step 2), graded against the golden `GoldContextSuite`.

The suite in each fixture's `context_gold.json` has existed since contracts 0.1.0 and
nothing in this repository referenced it, because the thing it grades did not exist. It is
the reason these tests assert correctness rather than shape: `q1-draft-scene-6` says, in
span-exact and hash-checked terms, what the packet for the mystery's resolution scene must
contain and what it must not.

**What the golden case does and does not measure here.** Both fixture books are six scenes of
roughly 120 words, and the query's budget is 6,000 tokens — so mandatory *recall* is not
under pressure and a packet that included everything would pass it. What is not free, and is
what these tests are really pinning: the forbidden POV leak, the state-record resource kinds,
and the fact that omissions are recorded rather than silent. Recall under a budget that
actually binds is measured separately, and honestly — see the budget tests below, which
assert that the packet stays inside its ceiling and says what it dropped, not that it dropped
the right things. The first-party endurance tests exercise survival and omission across long
serials; neither suite pretends that deterministic retention is a prose-quality score.
"""

from __future__ import annotations

import json

import litharness_contracts as lc
import pytest

from litharness.adapters.contracts_fixtures import (
    FIXTURE_IDS,
    fixture_context_gold,
    fixture_manuscript,
    fixture_plans,
)
from litharness.domain import context as context_mod
from litharness.domain.context import (
    CONSTRAINTS,
    FACTS,
    HISTORY,
    PREMISE,
    PRIOR_PROSE,
    THREADS,
    ContextBudgetTooSmall,
    assemble,
    count_tokens,
)
from litharness.domain.extraction import SHEET_PREDICATE
from litharness.domain.nodes import Node, NodeKind
from litharness.domain.revision import Revision, build_revision, import_manuscript
from litharness.domain.text import content_hash
from tests.conftest import BOOK_ID, BRANCH_ID, PROJECT_ID, make_revision, meta
from tests.test_state import load_state

#: Operations the assembler answers. The suite also carries `evaluate` and `repair` cases,
#: which nothing here can serve — there is no evaluation and no repair path in LitHarness.
#: Pinned as a set so *adding* one without grading it against the gold suite fails this file
#: rather than passing silently, which is the failure mode §10's whole calibration section
#: exists to prevent.
SUPPORTED_OPERATIONS = {lc.ContextOperation.DRAFT_SCENE}
UNSUPPORTED_OPERATIONS = {lc.ContextOperation.EVALUATE, lc.ContextOperation.REPAIR}


def load_book(fixture_id: str) -> Revision:
    """The fixture with its prose intact — the state the golden queries were written for.

    `import` clears scene prose so the book is draftable, which is right for the loop and
    wrong for grading a packet: `q1-draft-scene-6` asks what scene 6 should be told about
    scenes 1-5, and the answer is empty if scenes 1-5 have been emptied. This is exactly what
    `--keep-content` is for.
    """
    source = lc.parse_artifact(
        lc.ManuscriptRevision,
        json.loads(fixture_manuscript(fixture_id).read_text(encoding="utf-8")),
    )
    return import_manuscript(source, preserve_content=True).revision


def load_plan_items(fixture_id: str) -> list[lc.PlanItem]:
    snapshot = lc.parse_artifact(
        lc.PlanSnapshot, json.loads(fixture_plans(fixture_id).read_text(encoding="utf-8"))
    )
    return list(snapshot.items)


def load_gold(fixture_id: str) -> lc.GoldContextSuite:
    return lc.parse_artifact(
        lc.GoldContextSuite,
        json.loads(fixture_context_gold(fixture_id).read_text(encoding="utf-8")),
    )


def packet_for_case(fixture_id: str, case: lc.GoldContextCase) -> context_mod.ContextPacket:
    query = case.query
    return assemble(
        load_book(fixture_id),
        query.target.logical_id,
        plan_items=load_plan_items(fixture_id),
        state_records=load_state(fixture_id).records,
        query_id=query.query_id,
        pov_character_id=query.pov_character_id,
        token_budget=query.token_budget,
    )


# -- the golden suite ----------------------------------------------------------------------


def graded_cases() -> list[tuple[str, lc.GoldContextCase]]:
    return [
        (fixture_id, case)
        for fixture_id in FIXTURE_IDS
        for case in load_gold(fixture_id).cases
        if case.query.operation in SUPPORTED_OPERATIONS
    ]


def test_the_gold_suite_contains_a_draft_scene_case_to_grade() -> None:
    """A guard on the guard. If the fixture's operations ever change, every parametrised
    test below would silently collapse to zero cases and the file would still pass."""
    assert [case.query.query_id for _, case in graded_cases()] == ["q1-draft-scene-6"]


def test_the_operations_this_assembler_cannot_serve_are_named_rather_than_ignored() -> None:
    """Four of the five golden cases are `evaluate` and `repair`, and nothing in LitHarness
    answers either. Skipping them silently would let "the packet passes the gold suite" mean
    "it passes the one fifth of it we implemented"."""
    present = {
        case.query.operation for fixture_id in FIXTURE_IDS for case in load_gold(fixture_id).cases
    }
    assert present == SUPPORTED_OPERATIONS | UNSUPPORTED_OPERATIONS
    ungraded = [
        case.query.query_id
        for fixture_id in FIXTURE_IDS
        for case in load_gold(fixture_id).cases
        if case.query.operation not in SUPPORTED_OPERATIONS
    ]
    assert ungraded == ["q2-evaluate-timeline", "q3-repair-bruno", "q1-audit-gold", "q2-repair-hp"]


@pytest.mark.parametrize(
    ("fixture_id", "case"),
    graded_cases(),
    ids=[f"{fixture_id}:{case.query.query_id}" for fixture_id, case in graded_cases()],
)
def test_the_packet_carries_every_mandatory_item(fixture_id: str, case: lc.GoldContextCase) -> None:
    packet = packet_for_case(fixture_id, case)
    missing = [
        target.reason for target in case.mandatory if not _satisfies(packet, target, fixture_id)
    ]
    assert missing == []


@pytest.mark.parametrize(
    ("fixture_id", "case"),
    graded_cases(),
    ids=[f"{fixture_id}:{case.query.query_id}" for fixture_id, case in graded_cases()],
)
def test_the_packet_carries_no_forbidden_item(fixture_id: str, case: lc.GoldContextCase) -> None:
    packet = packet_for_case(fixture_id, case)
    leaked = [target.reason for target in case.forbidden if _satisfies(packet, target, fixture_id)]
    assert leaked == []


def _satisfies(
    packet: context_mod.ContextPacket, target: lc.GoldContextTarget, fixture_id: str
) -> bool:
    if target.ref is not None:
        return packet.contains_ref(target.ref.logical_id, target.ref.kind)
    assert target.span is not None
    return packet.contains_span(target.span.source.logical_id, target.span.start, target.span.end)


def test_the_mandatory_span_offsets_are_the_fixtures_own() -> None:
    """Containment makes the span check easy to satisfy accidentally, so this pins that the
    offsets address the text the fixture says they do. If the manuscript were decoded with
    the wrong codec — the cp1252 failure `cli import` guards against — the offsets would
    shift and the hash would stop matching, and the containment test alone would not notice.
    """
    book = load_book("mystery")
    case = next(
        item for item in load_gold("mystery").cases if item.query.query_id == "q1-draft-scene-6"
    )
    spans = [target.span for target in case.mandatory if target.span is not None]
    assert spans, "q1 is the distant-callback case and must carry a prose span"
    for span in spans:
        content = book.node(span.source.logical_id).content
        assert content is not None
        assert content_hash(content[span.start : span.end]) == span.content_sha256


def test_the_motive_span_is_reached_through_scene_four_specifically() -> None:
    """The distant-callback property, stated as the fixture states it: the mandatory items
    for scene 6 come from scenes 1, 2 and 4, not from scene 5. A packet carrying only the
    immediately preceding scene — the naive recent-window baseline — would fail this."""
    case = next(
        item for item in load_gold("mystery").cases if item.query.query_id == "q1-draft-scene-6"
    )
    packet = packet_for_case("mystery", case)
    assert packet.contains_ref("scene-4")
    assert packet.contains_ref("scene-1")


def test_the_private_knowledge_is_omitted_for_the_stated_reason_not_by_accident() -> None:
    """Absence proves nothing on its own — a packet that dropped the record for want of
    budget, or never looked at state at all, would also "pass" the forbidden check. This
    asserts the record was considered and excluded *because of the POV*."""
    case = next(
        item for item in load_gold("mystery").cases if item.query.query_id == "q1-draft-scene-6"
    )
    packet = packet_for_case("mystery", case)
    reasons = {item.source_logical_id: item.reason for item in packet.omitted}
    assert reasons["rec-brandt-knows-letter"] == "not visible to POV mara"
    # And the record Mara *does* know is in, so the filter is not simply excluding knowledge.
    assert packet.contains_ref("rec-mara-knows-floorboard")


# -- what the old prompt was missing ---------------------------------------------------------


def test_the_constraint_that_names_this_scene_reaches_the_prompt() -> None:
    """The concrete gap this slice closed. Two locked plan items bear directly on the
    mystery's scene 6 — a motif that repeats in it by number, and a promise the book owes
    before it ends — and both sat in the store, parsed by `constraints_of`, read by nothing.
    """
    packet = assemble(
        load_book("mystery"),
        "scene-6",
        plan_items=load_plan_items("mystery"),
        state_records=load_state("mystery").records,
        pov_character_id="mara",
    )
    rendered = packet.render()
    assert "rain-on-glass motif repeats deliberately in scenes 1, 3, and 6" in rendered
    assert "sealed letter must be read aloud at the will reading" in rendered


def test_the_premise_is_still_there() -> None:
    packet = assemble(load_book("mystery"), "scene-6", plan_items=load_plan_items("mystery"))
    assert len(packet.sections[PREMISE]) == 1
    assert "locked-room mystery" in packet.render()


def test_a_book_with_no_plan_yields_no_premise_section_rather_than_a_placeholder() -> None:
    packet = assemble(load_book("mystery"), "scene-6")
    assert packet.sections.get(PREMISE, ()) == ()


# -- prior prose ------------------------------------------------------------------------------


def test_only_scenes_before_the_target_are_packed() -> None:
    packet = assemble(make_revision(), "scene-4")
    assert [item.source_logical_id for item in packet.sections[PRIOR_PROSE]] == [
        "scene-1",
        "scene-2",
        "scene-3",
    ]


def test_prose_is_rendered_in_reading_order_even_though_it_is_selected_backwards() -> None:
    """Selection order is not render order, and conflating them is the bug the module
    docstring exists to prevent: dropping the oldest scene under a tight budget is right,
    and handing the generator scene 5 before scene 1 is not."""
    packet = assemble(make_revision(), "scene-6")
    assert [item.source_logical_id for item in packet.sections[PRIOR_PROSE]] == [
        f"scene-{n}" for n in range(1, 6)
    ]
    rendered = packet.render()
    positions = [rendered.index(item.text) for item in packet.sections[PRIOR_PROSE]]
    assert positions == sorted(positions)


def test_an_undrafted_scene_contributes_nothing() -> None:
    """The live case: on a regenerating book, scenes after the head are empty. An empty node
    must not become an empty prose item, which would spend a section heading on nothing."""
    revision = make_revision()
    emptied = Revision(
        book_id=revision.book_id,
        branch_id=revision.branch_id,
        nodes=tuple(
            node
            if node.logical_id in {"book", "scene-1"}
            else Node(
                logical_id=node.logical_id,
                kind=node.kind,
                position_key=node.position_key,
                parent_logical_id=node.parent_logical_id,
                title=node.title,
            )
            for node in revision.nodes
        ),
    )
    packet = assemble(emptied, "scene-6")
    assert [item.source_logical_id for item in packet.sections[PRIOR_PROSE]] == ["scene-1"]


def test_the_first_scene_of_a_book_gets_an_empty_prose_section() -> None:
    packet = assemble(load_book("mystery"), "scene-1")
    assert packet.sections[PRIOR_PROSE] == ()


# -- the budget --------------------------------------------------------------------------------


def test_the_packet_never_exceeds_its_budget() -> None:
    """The universal property a priority-packer can promise; endurance tests cover survival."""
    for budget in (1800, 2000, 2400, 3000, 6000):
        packet = assemble(
            load_book("mystery"),
            "scene-6",
            plan_items=load_plan_items("mystery"),
            state_records=load_state("mystery").records,
            token_budget=budget,
            reserved_output=1500,
        )
        assert packet.used_tokens <= budget - 1500, budget


def test_everything_dropped_is_recorded_with_a_reason() -> None:
    """The whole of what a baseline honestly owes. A packet that silently dropped the
    constraint naming this scene would be worse than the bare prompt it replaces, because
    the bare prompt was at least obviously empty."""
    full = assemble(
        load_book("mystery"),
        "scene-6",
        plan_items=load_plan_items("mystery"),
        state_records=load_state("mystery").records,
        token_budget=6000,
    )
    squeezed = assemble(
        load_book("mystery"),
        "scene-6",
        plan_items=load_plan_items("mystery"),
        state_records=load_state("mystery").records,
        token_budget=1700,
        reserved_output=1500,
    )
    assert len(squeezed.items) < len(full.items)
    dropped = {item.source_logical_id for item in full.items} - {
        item.source_logical_id for item in squeezed.items
    }
    recorded = {item.source_logical_id for item in squeezed.omitted}
    assert dropped and dropped <= recorded


def test_prose_is_what_goes_first_under_pressure() -> None:
    """Priority order, asserted rather than described: the director's constraints and the
    book's open threads are small and load-bearing; prose is large and partly redundant with
    the facts extracted from it."""
    packet = assemble(
        load_book("mystery"),
        "scene-6",
        plan_items=load_plan_items("mystery"),
        state_records=load_state("mystery").records,
        token_budget=1700,
        reserved_output=1500,
    )
    assert packet.sections[CONSTRAINTS], "constraints must outrank prose"
    assert packet.sections[PRIOR_PROSE] == ()


def test_prose_is_dropped_oldest_first() -> None:
    """The recent-window baseline: scene 5 matters more to scene 6 than scene 1 does."""
    packet = assemble(
        load_book("mystery"),
        "scene-6",
        token_budget=1700,
        reserved_output=1500,
    )
    kept = [item.source_logical_id for item in packet.sections[PRIOR_PROSE]]
    assert kept, "a budget with no plan or state to spend on should hold some prose"
    assert kept[-1] == "scene-5"


def test_a_budget_too_small_for_the_premise_refuses_rather_than_dropping_it() -> None:
    """`plans.py` records why: a book drafted without a premise produces six scenes of
    plausible prose about nothing, and no gate in this system can detect that. So this is a
    refusal an operator sees, not an omission buried in a list."""
    with pytest.raises(ContextBudgetTooSmall, match="premise"):
        assemble(
            load_book("mystery"),
            "scene-6",
            plan_items=load_plan_items("mystery"),
            token_budget=1510,
            reserved_output=1500,
        )


def test_output_tokens_are_reserved_out_of_the_budget() -> None:
    """A budget spent entirely on input leaves no room for the scene, and discovering that
    at the provider is discovering it after paying for it."""
    generous = assemble(load_book("mystery"), "scene-6", token_budget=3000, reserved_output=0)
    reserved = assemble(load_book("mystery"), "scene-6", token_budget=3000, reserved_output=2500)
    assert reserved.used_tokens < generous.used_tokens


# -- accounting and projection -------------------------------------------------------------------


def test_token_counts_are_the_regex_v1_approximation() -> None:
    """The named local approximation keeps budget accounting deterministic and auditable."""
    assert context_mod.COUNTER_ID == "regex-v1"
    assert count_tokens("Mara laid the new will on the desk.") == 9
    assert count_tokens("") == 0


def test_the_packets_token_total_is_the_sum_of_its_items() -> None:
    packet = assemble(
        load_book("mystery"),
        "scene-6",
        plan_items=load_plan_items("mystery"),
        state_records=load_state("mystery").records,
    )
    assert packet.used_tokens == sum(item.tokens for item in packet.items)
    assert packet.used_tokens > 0


def test_the_packet_projects_onto_the_contract() -> None:
    """The contract projection makes the packet an auditable artifact, not a private string."""
    packet = assemble(
        load_book("mystery"),
        "scene-6",
        plan_items=load_plan_items("mystery"),
        state_records=load_state("mystery").records,
        query_id="q1-draft-scene-6",
        pov_character_id="mara",
    )
    projected = packet.to_contract(
        meta("context_packet", "packet-1"), project_id=PROJECT_ID, packet_id="packet-1"
    )
    assert projected.query_id == "q1-draft-scene-6"
    assert projected.budget.used == packet.used_tokens
    assert projected.budget.reserved_output == packet.reserved_output
    assert [section.name for section in projected.sections] == [
        PREMISE,
        CONSTRAINTS,
        THREADS,
        FACTS,
        PRIOR_PROSE,
    ]
    # The rejected candidates are on the artifact, not only in the log — an omission a
    # consumer cannot see is an omission that did not happen, as far as the consumer knows.
    assert any(
        rejected.item_id == "rec-brandt-knows-letter" for rejected in projected.rejected_candidates
    )
    # And it survives a round trip through the wire, which is what "artifact" means.
    assert lc.from_jsonable(lc.ContextPacket, lc.to_jsonable(projected)).packet_id == "packet-1"


def test_assembly_is_deterministic() -> None:
    """§13's reproducibility levels are what let a recorded policy decision mean anything
    later, and a packet that packed differently on two runs would make the prompt — and
    therefore the candidate — unreproducible from the same inputs."""
    kwargs = {
        "plan_items": load_plan_items("mystery"),
        "state_records": load_state("mystery").records,
        "pov_character_id": "mara",
    }
    first = assemble(load_book("mystery"), "scene-6", **kwargs)  # type: ignore[arg-type]
    second = assemble(load_book("mystery"), "scene-6", **kwargs)  # type: ignore[arg-type]
    assert first.render() == second.render()
    assert [item.item_id for item in first.items] == [item.item_id for item in second.items]


def test_the_litrpg_book_assembles_too() -> None:
    """§17 Stage 1 is graded on both fixtures, and the litrpg one has no `draft_scene` gold
    case — so this asserts the assembler runs over it and produces something, which is the
    honest claim available without ground truth."""
    packet = assemble(
        load_book("litrpg"),
        "scene-6",
        plan_items=load_plan_items("litrpg"),
        state_records=load_state("litrpg").records,
    )
    assert packet.sections[PREMISE]
    assert packet.sections[PRIOR_PROSE]
    assert packet.used_tokens > 0


# -- rendering ------------------------------------------------------------------------------------


def test_sections_are_labelled_so_a_constraint_is_not_mistaken_for_prose() -> None:
    packet = assemble(
        load_book("mystery"),
        "scene-6",
        plan_items=load_plan_items("mystery"),
        state_records=load_state("mystery").records,
        pov_character_id="mara",
    )
    rendered = packet.render()
    assert "Premise:" in rendered
    assert "Locked constraints and promises" in rendered
    assert "Open threads the book still owes" in rendered
    assert "Established facts (POV: mara) — world truth" in rendered
    assert "The story so far" in rendered


def test_an_empty_packet_renders_to_nothing_rather_than_to_headings() -> None:
    empty = assemble(
        Revision(
            book_id=BOOK_ID,
            branch_id=BRANCH_ID,
            nodes=(Node(logical_id="book", kind=NodeKind.BOOK, position_key="010"),),
        ),
        "scene-1",
    )
    assert empty.render() == ""


# -- the evicted-context slot ------------------------------------------------------------


def _premise() -> lc.PlanItem:
    return lc.PlanItem(
        logical_id="premise",
        kind=lc.PlanKind.PREMISE,
        text="A long book.",
        authority=lc.StateAuthority.AUTHOR_LOCKED,
    )


#: A budget small enough to make the packet evict. The default is 200,000 since §132 and does
#: not bind on a book this size, so every test of the eviction path names its own.
BINDING_BUDGET = 6000


def _long_book(scenes: int, words: int) -> Revision:
    """A book whose scenes are the length a capable generator actually writes."""
    nodes = [Node(logical_id="book", kind=NodeKind.BOOK, position_key="010")]
    for index in range(1, scenes + 1):
        nodes.append(
            Node(
                logical_id=f"s{index}",
                kind=NodeKind.SCENE,
                position_key=f"{index:03d}0",
                parent_logical_id="book",
                content=f"Scene {index}. " + " ".join(["word"] * words),
            )
        )
    nodes.append(
        Node(
            logical_id="target",
            kind=NodeKind.SCENE,
            position_key="9990",
            parent_logical_id="book",
        )
    )
    return build_revision(BOOK_ID, BRANCH_ID, nodes)


def test_an_evicted_scene_arrives_as_its_summary_instead_of_as_an_omission() -> None:
    """The slot the budget's eviction leaves, filled.

    At the 172-word scenes this system used to write, the 6,000-token budget never bound and
    the eviction path was unreachable — `plan/stage-0-decisions.md` §47 records the counter
    staying at zero for every six-scene fixture, "which is exactly why this limit went
    unnoticed". At the lengths a capable generator produces it binds around scene five, and
    from there the generator was handed the three scenes behind it and nothing at all about
    the rest of the book it had written.
    """
    revision = _long_book(scenes=12, words=400)
    premise = [_premise()]

    # **Explicit since §132**: the default is 200,000 and never binds on a book this size,
    # which is the point of raising it. The eviction path it leaves behind is for a long
    # serial and is still tested, at a budget chosen to bind.
    bare = assemble(revision, "target", plan_items=premise, token_budget=BINDING_BUDGET)
    evicted = {omission.source_logical_id for omission in bare.omitted}
    assert evicted, "the budget must actually bind, or this test proves nothing"

    summaries = {logical_id: f"{logical_id} happened." for logical_id in evicted}
    packed = assemble(
        revision,
        "target",
        plan_items=premise,
        summaries=summaries,
        token_budget=BINDING_BUDGET,
    )

    covered = {item.source_logical_id for item in packed.sections[context_mod.SUMMARIES]}
    assert covered, "the section exists to be filled and must actually fill"
    # Every scene that was dropped for budget is now represented, and is no longer reported
    # as dropped — a recorded omission for a scene the generator was told the substance of
    # would make `rejected_candidates` say the opposite of what happened.
    assert covered == evicted
    assert not {o.source_logical_id for o in packed.omitted} & covered
    assert packed.used_tokens <= packed.token_budget - packed.reserved_output


def test_a_summary_never_appears_beside_the_prose_it_summarises() -> None:
    """The same information twice, at the generator's expense, is the obvious way to get
    this wrong: the summary is for the scenes that did *not* fit."""
    revision = _long_book(scenes=12, words=400)
    premise = [_premise()]
    everything = {f"s{index}": f"s{index} happened." for index in range(1, 13)}
    packed = assemble(
        revision,
        "target",
        plan_items=premise,
        summaries=everything,
        token_budget=BINDING_BUDGET,
    )

    whole = {item.source_logical_id for item in packed.sections[context_mod.PRIOR_PROSE]}
    summarised = {item.source_logical_id for item in packed.sections[context_mod.SUMMARIES]}
    assert whole, "the nearest scenes must still arrive in full"
    assert summarised, "and the far ones in summary"
    assert not whole & summarised


def test_a_book_with_no_summaries_packs_exactly_as_it_did_before() -> None:
    """The reserve is only as large as the summaries on hand, so the section is additive.

    Without this the change would quietly shrink every existing packet by a quarter — a
    regression invisible to every test that does not count tokens.
    """
    revision = _long_book(scenes=12, words=400)
    premise = [_premise()]
    # **Explicit since §132**: the default is 200,000 and never binds on a book this size,
    # which is the point of raising it. The eviction path it leaves behind is for a long
    # serial and is still tested, at a budget chosen to bind.
    bare = assemble(revision, "target", plan_items=premise, token_budget=BINDING_BUDGET)
    empty = assemble(
        revision,
        "target",
        plan_items=premise,
        summaries={},
        token_budget=BINDING_BUDGET,
    )
    assert [item.source_logical_id for item in bare.items] == [
        item.source_logical_id for item in empty.items
    ]
    assert bare.used_tokens == empty.used_tokens


def test_the_summary_block_tells_the_generator_not_to_copy_its_register() -> None:
    """§1a.3 item 6 names "summarising instead of dramatising" as an AI tell, and this
    section hands the generator a block of exactly that register directly above the
    instruction to write. Naming the trap in the prompt is free; it is not evidence that it
    works, and the craft instrumentation on post-eviction scenes is what would measure it."""
    revision = _long_book(scenes=12, words=400)
    premise = [_premise()]
    packed = assemble(
        revision,
        "target",
        plan_items=premise,
        summaries={f"s{index}": f"s{index} happened." for index in range(1, 13)},
        token_budget=BINDING_BUDGET,
    )
    rendered = packed.render()
    assert "in summary" in rendered
    assert "never in this register" in rendered
    # And the two blocks stay distinguishable, so the model is not handed an undifferentiated
    # wall in which a paraphrase reads as the book's own prose.
    assert rendered.index("in summary") < rendered.index("The story so far, in full")


def test_a_summary_is_derived_and_never_accepted_canon() -> None:
    """A model wrote it, from prose that is canon. `state` records stay the only route to
    accepted canon, so a summary's paraphrase cannot be cited back as an established fact."""
    revision = _long_book(scenes=12, words=400)
    premise = [_premise()]
    packed = assemble(
        revision,
        "target",
        plan_items=premise,
        summaries={f"s{index}": f"s{index} happened." for index in range(1, 13)},
        token_budget=BINDING_BUDGET,
    )
    for item in packed.sections[context_mod.SUMMARIES]:
        assert item.authority is lc.StateAuthority.DERIVED
        assert item.kind is lc.ContextItemKind.SUMMARY
        assert item.span is None, "a summary is not a quotation of a span of the book"


def test_a_sheet_declaration_never_reaches_a_packet() -> None:
    """What configures the telling is not part of the told.

    Measured on the first reseeded Serial Pilot rehearsal: the book's own `status_sheet`
    declaration arrived in the scene's Established facts block as
    `silas status_sheet fields=[{'label': 'Loop', 'name': 'loop'}...]`, which hands a writer a
    configuration blob and calls it a fact about the world. It is the narrow instance of the
    defect `plan/state-model-abilities.md` §2 names, and the narrow fix is this exclusion.
    """
    declaration = lc.StateRecord(
        record_id="rec-sheet",
        kind=lc.StateRecordKind.WORLD_RULE,
        subject="rook",
        predicate=SHEET_PREDICATE,
        value={"fields": [{"name": "loop", "label": "Loop"}]},
        authority=lc.StateAuthority.ACCEPTED_CANON,
        pov_visibility=[],
        evidence=[],
    )
    records = [*load_state("litrpg").records, declaration]

    packet = assemble(load_book("litrpg"), "scene-6", state_records=records, token_budget=8000)

    assert SHEET_PREDICATE not in packet.render()
    assert packet.sections.get(FACTS), "ordinary world facts must still arrive"
    # And it is not an omission: `context_omitted` is the counter that says a scene was
    # written without part of its book, and a configuration record was never part of it.
    assert not [item for item in packet.omitted if item.source_logical_id == "rec-sheet"]


def test_character_sheets_cannot_reintroduce_future_or_private_state() -> None:
    """The cast is another rendering of state, not a route around its visibility gate."""
    role = lc.StateRecord(
        record_id="role-mara",
        kind=lc.StateRecordKind.ASSERTION,
        subject="mara",
        predicate="entity_role",
        value="protagonist",
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )
    visible_want = lc.StateRecord(
        record_id="want-now",
        kind=lc.StateRecordKind.ASSERTION,
        subject="mara",
        predicate="wants",
        value="find the key",
        story_position=lc.StoryPosition(order_key="s1"),
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )
    future_want = lc.StateRecord(
        record_id="want-later",
        kind=lc.StateRecordKind.ASSERTION,
        subject="mara",
        predicate="wants",
        value="burn the house",
        story_position=lc.StoryPosition(order_key="s9"),
        authority=lc.StateAuthority.ACCEPTED_CANON,
    )
    private_tie = lc.StateRecord(
        record_id="private-tie",
        kind=lc.StateRecordKind.RELATIONSHIP,
        subject="mara",
        predicate="betrayed",
        object_ref="brandt",
        story_position=lc.StoryPosition(order_key="s1"),
        authority=lc.StateAuthority.ACCEPTED_CANON,
        pov_visibility=["brandt"],
    )

    packet = assemble(
        make_revision(),
        "scene-1",
        state_records=[role, visible_want, future_want, private_tie],
        story_time_cutoff="s2",
        pov_character_id="mara",
        token_budget=8000,
    )
    rendered = packet.render()

    assert "find the key" in rendered
    assert "burn the house" not in rendered
    assert "betrayed" not in rendered
    assert not packet.contains_ref("want-later")
    omissions = {item.source_logical_id: item.reason for item in packet.omitted}
    assert set(omissions) == {"private-tie", "want-later"}
    assert "POV" in omissions["private-tie"]
    assert "not yet established" in omissions["want-later"]


def test_replaced_character_state_is_labelled_as_history_not_as_current_fact() -> None:
    records = [
        lc.StateRecord(
            record_id="role-mara",
            kind=lc.StateRecordKind.ASSERTION,
            subject="mara",
            predicate="entity_role",
            value="protagonist",
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
        lc.StateRecord(
            record_id="want-early",
            kind=lc.StateRecordKind.ASSERTION,
            subject="mara",
            predicate="wants",
            value="escape",
            story_position=lc.StoryPosition(order_key="s1"),
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
        lc.StateRecord(
            record_id="want-now",
            kind=lc.StateRecordKind.ASSERTION,
            subject="mara",
            predicate="wants",
            value="return",
            story_position=lc.StoryPosition(order_key="s3"),
            authority=lc.StateAuthority.ACCEPTED_CANON,
        ),
    ]

    packet = assemble(
        make_revision(),
        "scene-1",
        state_records=records,
        story_time_cutoff="s3",
        project_state_changes=True,
        token_budget=8000,
    )

    assert "wants: return" in packet.render()
    assert "At s1: mara wants escape" in packet.render()
    assert "want-early" not in {item.item_id for item in packet.sections[FACTS]}
    assert "want-early" in {item.item_id for item in packet.sections[HISTORY]}
