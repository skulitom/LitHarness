"""Frozen input locations must survive repetition, system routing and shelf insertion."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

import litharness_contracts as lc
import pytest

from litharness.application import planner
from litharness.application.prompt_sources import PromptSources
from litharness.domain import context as ctx
from litharness.domain import writers
from tests import test_prompt_budget as examples


def request_case(shelf=False):
    repeated = "Réad the sign.\nWait."
    sections = {}
    for section in (ctx.PREMISE, ctx.CONSTRAINTS, ctx.RULES, ctx.FACTS, ctx.HIDDEN):
        sections[section] = (
            ctx.PackedItem(
                item_id=section,
                kind=lc.ContextItemKind.FACT,
                source_logical_id="source:" + section,
                source_kind=lc.ResourceKind.UNKNOWN,
                text=repeated,
                tokens=5,
                pov_visibility=("observer",),
            ),
        )
    return {
        "book_title": "A test",
        "packet": replace(examples._PACKET, sections=sections),
        "status_example": examples._STATUS_EXAMPLE,
        "status_moved": examples._STATUS_MOVED,
        "progression": examples._PROGRESSION,
        "standing": examples._STANDING,
        "standing_line": examples._STANDING_LINE,
        "target_words": 900,
        "criteria": examples._CRITERIA,
        "offer_line": examples._OFFER_LINE,
        "gain_line": examples._GAIN_LINE,
        "change_line": examples._CHANGE_LINE,
        "notices": (examples._NOTICE_LINE,),
        "readouts": (examples._READOUT_LINE,),
        "scene_plan": "  Read, then act.  ",
        "writer": writers.build("Test writer", "A short writer dossier."),
        "shelf": examples._SHELF if shelf else None,
    }


@pytest.mark.parametrize("shelf", [False, True])
def test_composed_prompt_preserves_pre_instrumentation_bytes(shelf):
    # Prompt bytes retain the original instrumentation fixture. System hashes include
    # the 2026-09-08 literal-magic clarification and replacement precision policy.
    expected = {
        False: (
            "ee85221d4a4f6d5ad2ec13198f74e8fdd764b47cb57e0b90677a073208d92db5",
            "37be520580efa008ce4d4d302a46bab6d38ca33eeea8d21034fe27d39e065f10",
        ),
        True: (
            "8e328a85286978bda573e2eebe8af69c0f43d8f86e441aced1640d89e573a1b0",
            "1df0c553b559be3c16e529e6d2fafc221bae23467fbacd71073abb3b91113385",
        ),
    }
    system, prompt = planner.render_prompt(examples._BEAT, **request_case(shelf))
    assert tuple(sha256(text.encode()).hexdigest() for text in (system, prompt)) == expected[shelf]


@pytest.mark.parametrize("shelf", [False, True])
def test_every_selected_item_maps_to_its_insertion_not_a_matching_copy(shelf):
    mapping = {}
    system, prompt = planner.render_prompt(
        examples._BEAT, **request_case(shelf), source_map=mapping
    )
    stages = {"system": system, "prompt": prompt}
    items = [entry for entry in mapping["entries"] if entry["kind"] == "context_item"]
    assert len(items) == 5
    assert {entry["section"] for entry in items if entry["stage"] == "system"} == {
        ctx.CONSTRAINTS,
        ctx.RULES,
    }
    assert {entry["section"] for entry in items if entry["stage"] == "prompt"} == {
        ctx.PREMISE,
        ctx.FACTS,
        ctx.HIDDEN,
    }
    assert len({(entry["stage"], entry["start"], entry["end"]) for entry in items}) == 5
    for entry in items:
        assert stages[entry["stage"]][entry["start"] : entry["end"]] == "Réad the sign.\nWait."
        assert entry["source"]["source_logical_id"] == "source:" + entry["section"]
    if shelf:
        shelf_end = next(e["end"] for e in mapping["entries"] if e["section"] == "exemplar_shelf")
        assert all(e["start"] >= shelf_end for e in items if e["stage"] == "prompt")
    for entry in mapping["entries"]:
        actual = stages[entry["stage"]][entry["start"] : entry["end"]]
        assert sha256(actual.encode()).hexdigest() == entry["sha256"]
    plan = next(e for e in mapping["entries"] if e["kind"] == "scene_plan")
    assert prompt[plan["start"] : plan["end"]] == " This scene: Read, then act."
    assert plan["source"]["rendered_argument_sha256"] == sha256(b"  Read, then act.  ").hexdigest()


def test_builder_rejects_drift_in_context_insertion_and_final_text():
    sources = PromptSources()
    rendered = request_case()["packet"].render_with_sources()
    with pytest.raises(ValueError, match="inserted fragment"):
        sources.append("prompt", "", "different", "context", rendered=rendered)
    sources = PromptSources()
    sources.append("prompt", "", "original", "test")
    with pytest.raises(ValueError, match="changed"):
        sources.finish("", "modified", {})


def test_empty_context_remains_a_valid_empty_span():
    mapping = {}
    planner.render_prompt(
        examples._BEAT, book_title=None, packet=examples._PACKET, source_map=mapping
    )
    entry = next(e for e in mapping["entries"] if e["section"] == "context")
    assert entry["start"] == entry["end"] == 0
