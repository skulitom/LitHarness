"""Keep paired history coverage, reference boundaries and repeated requests explicit."""

import importlib.util
import json
import random
from pathlib import Path

import pytest

from litharness.application import discovery
from litharness.domain.generation import CompletionRequest

PATH = (
    Path(__file__).resolve().parents[1]
    / "research/quality-measurement/invention-plan-memory-20260912/run.py"
)
SPEC = importlib.util.spec_from_file_location("invention_plan_memory_experiment", PATH)
assert SPEC is not None and SPEC.loader is not None
experiment = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(experiment)


def test_full_history_keeps_exact_paired_fields_and_order_without_mutating_sources():
    sources = [(f'Premise {i} with "quotes"', {
        "world": f"WORLD_{i}", "opening": f"OPENING_{i}", "growth": f"GROWTH_{i}",
    }) for i in range(2)]
    before = json.dumps(sources)
    histories = experiment.history_pair(sources)
    assert histories["short"] == [{"premise": p} for p, _ in sources]
    assert histories["full"] == [{"premise": p, **plan} for p, plan in sources]
    assert json.dumps(sources) == before
    with pytest.raises(ValueError):
        experiment.history_pair([("Premise", {**sources[0][1], "probability": 0.01})])


def test_only_full_expansion_receives_plans_and_instructions_are_identical():
    histories = experiment.history_pair([("OLD_PREMISE", {
        "world": "OLD_WORLD", "opening": "OLD_OPENING", "growth": "OLD_GROWTH",
    })])
    clean = discovery.render_request("NEW_PREMISE", person="third")
    short = experiment.expansion_request("short", "NEW_PREMISE", histories, discovery)
    full = experiment.expansion_request("full", "NEW_PREMISE", histories, discovery)
    assert experiment.expansion_request("clean", "NEW_PREMISE", histories, discovery) == clean
    assert short.system == full.system == clean.system
    assert short.schema == full.schema == clean.schema
    assert short.prompt.endswith(clean.prompt) and full.prompt.endswith(clean.prompt)
    assert "OLD_PREMISE" in short.prompt and "OLD_PREMISE" in full.prompt
    assert "OLD_WORLD" not in short.prompt and "OLD_WORLD" in full.prompt
    assert short.prompt.replace(json.dumps(histories["short"]), "HISTORY") == full.prompt.replace(
        json.dumps(histories["full"]), "HISTORY"
    )
    assert "OLD_PREMISE" not in clean.prompt
    assert experiment.expansion_request("full", "NEW_PREMISE", histories, discovery) == full
    with pytest.raises(ValueError):
        experiment.expansion_request("unknown", "NEW_PREMISE", histories, discovery)


def test_initial_invention_uses_only_short_history_and_opaque_prefix():
    histories = experiment.history_pair([("OLD_PREMISE", {
        "world": "OLD_WORLD", "opening": "OLD_OPENING", "growth": "OLD_GROWTH",
    })])
    request = experiment.invention_request("OPAQUE_PREFIX", histories, CompletionRequest)
    assert request.system.startswith("OPAQUE_PREFIX\n\n")
    assert "OLD_PREMISE" in request.prompt and "OLD_WORLD" not in request.prompt
    assert experiment.EXPAND not in request.prompt and experiment.INVENT in request.prompt
    assert request.schema == experiment.parent.parent.SCHEMA


def test_selection_is_content_independent_and_repeat_order_reverses_each_premise():
    state = random.getstate()
    assert experiment.selected_index("12345") == random.Random(
        "invention-plan-memory.v1:12345"
    ).randrange(6)
    assert random.getstate() == state
    assert len(experiment.ORDER) + len(experiment.EXPANSIONS) == 14
    for block in ("1", "2"):
        orders = [[n.split("-")[0] for n in experiment.EXPANSIONS if n.endswith(f"-{block}-{r}")]
                  for r in (1, 2)]
        assert sorted(orders[0]) == sorted(experiment.ARMS)
        assert orders[1] == orders[0][::-1]


def test_transport_audit_requires_effective_schema_instruction_and_rejects_extra_text():
    request = CompletionRequest(
        prompt="TASK", system="SYSTEM", schema=experiment.parent.parent.SCHEMA
    )
    fields = {"transport.system": request.effective_system, "transport.prompt": request.prompt}
    assert all(experiment.transport_text_checks(request, fields).values())
    for wrong_system in (request.system, request.effective_system + "\nEXTRA_INSTRUCTION"):
        assert not experiment.transport_text_checks(
            request, {**fields, "transport.system": wrong_system}
        )["effective_system_equal"]
    assert not experiment.transport_text_checks(
        request, {**fields, "transport.prompt": "DIFFERENT_TASK"}
    )["prompt_equal"]
