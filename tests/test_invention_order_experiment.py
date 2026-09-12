"""The order experiment keeps a real baseline and exposes its exact treatment delta."""

from __future__ import annotations

import dataclasses
import importlib.util
from pathlib import Path

from litharness.application import discovery
from litharness.domain.invention import make_seed
from litharness.providers.codex_cli import CodexCliProvider
from litharness.providers.codex_schema import prepare_codex_schema


def module():
    path = Path(__file__).resolve().parents[1] / (
        "research/quality-measurement/invention-order-20260912/run.py"
    )
    spec = importlib.util.spec_from_file_location("order_experiment", path)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_order_comparison_changes_only_field_instruction_and_schema_order():
    experiment = module()
    seed = make_seed("98765432109876543210")
    baseline = experiment.request_for(seed, "control")
    opening = experiment.request_for(seed, "opening")
    assert baseline == discovery.render_request("", person="third", seed=seed)
    assert sorted(baseline.system.splitlines()) == sorted(opening.system.splitlines())
    assert dataclasses.replace(opening, system=baseline.system, schema=baseline.schema) == baseline
    assert list(baseline.schema["properties"]) == ["world", "opening", "growth"]
    assert list(prepare_codex_schema(opening.schema)["properties"]) == [
        "opening", "world", "growth",
    ]
    assert opening.schema["required"] == ["opening", "world", "growth"]
    assert opening.system.index("opening: ") < opening.system.index("world: ")


def test_pursuit_delta_keeps_genre_seed_settings_and_all_original_field_content():
    experiment = module()
    seed = make_seed("98765432109876543210")
    opening = experiment.request_for(seed, "opening")
    pursuit = experiment.request_for(seed, "pursuit")
    restored = pursuit.system.replace(experiment.PURSUIT + "\n", "", 1).replace(
        "in the four fields", "in the three fields",
    )
    assert restored == opening.system
    assert pursuit.system.startswith(seed.brief + "\n\n")
    assert dataclasses.replace(pursuit, system=opening.system, schema=opening.schema) == opening
    assert list(prepare_codex_schema(pursuit.schema)["properties"]) == [
        "pursuit", "opening", "world", "growth",
    ]
    assert pursuit.schema["required"] == ["pursuit", "opening", "world", "growth"]
    assert pursuit.system.index("pursuit: ") < pursuit.system.index("opening: ")
    assert set(experiment.ORDER) == {
        f"{arm}-{i}" for arm in ("control", "opening", "pursuit") for i in (1, 2, 3)
    }


def test_order_experiment_constructs_real_provider_without_dispatch(tmp_path):
    experiment = module()
    experiment.LOCAL = tmp_path
    provider = experiment.provider_for("uninvoked-binary")
    assert isinstance(provider, CodexCliProvider)
    assert provider.binary == "uninvoked-binary"
    assert provider.trace_directory == tmp_path / "transport"
