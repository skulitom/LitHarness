"""Model tiers per role on the one provider (§256): explicit, switchable, never a fallback."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pytest

from litharness import cli
from litharness.domain.generation import CompletionRequest, CompletionResult, Usage
from litharness.providers import CodexCliProvider, ProviderRegistry, selected_provider
from litharness.providers.routing import (
    CANDIDATE_ROLE_TIERS,
    PINNED_STRONG,
    PROVIDER_TIERS,
    TIERS,
    ModelRouting,
    codex_efforts,
    review_status,
)

REPO = Path(__file__).resolve().parents[1]

#: Profiles the pipeline sends, with the tier the candidate map gives each.
CANDIDATE_EXPECTED = {
    "architect.seed.v9": "standard",
    "architect.grow.v5": "standard",
    "mechanical": "strong",
    "title.availability.v0": "basic",
    "default": "strong",
    "prose": "strong",
    "writer.discovery.v14": "strong",
    "writer.concept.discovery.v9": "strong",
    "writer.concept.material.v2": "strong",
    "writer.concept.v1": "strong",
    "writer.concept.precision.v1": "strong",
    "writer.overview.concept.v2": "strong",
    "writer.title.v0": "strong",
    "planner.outline.v8": "strong",
    "planner.outline.structured.v4": "strong",
    "reviser.scene.v0": "strong",
    "director.v1": "strong",
    "reader.appetite.v0": "strong",
    "editorial.reader.v0": "strong",
}


@dataclass
class _Recorder:
    """A provider that records what it was asked, for the registry's routing."""

    name: str = "recorder"
    bills: bool = False
    seen: list[CompletionRequest] = field(default_factory=list)

    def health(self) -> bool:
        return True

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.seen.append(request)
        return CompletionResult(
            text="ok", provider=self.name, model=request.model or "adapter", usage=Usage()
        )


@pytest.mark.parametrize("provider", sorted(PROVIDER_TIERS))
def test_the_shipped_default_routes_nothing(provider: str) -> None:
    """No setting means every role stays on the adapter's own model: the request is untouched,
    so existing request digests and every stored run are unchanged."""
    routing = ModelRouting.from_environ(provider, {})
    for profile in CANDIDATE_EXPECTED:
        request = CompletionRequest(prompt="x", profile=profile)
        assert routing.route(request) is request


@pytest.mark.parametrize("provider", sorted(PROVIDER_TIERS))
def test_candidate_tiers_route_only_the_bookkeeping_roles(provider: str) -> None:
    routing = ModelRouting.from_environ(provider, {"LITHARNESS_MODEL_TIERS": "candidate"})
    for profile, tier in CANDIDATE_EXPECTED.items():
        assert routing.tier_for(profile) == tier, profile
        routed = routing.route(CompletionRequest(prompt="x", profile=profile))
        assert routed.model == PROVIDER_TIERS[provider][tier], profile


def test_every_tier_is_mapped_on_both_providers_so_either_can_run_alone() -> None:
    """A Claude-only or a Codex-only day needs every tier on both sides; strong is the adapter's
    own default on both."""
    assert set(PROVIDER_TIERS) == {"claude", "codex"}
    for tiers in PROVIDER_TIERS.values():
        assert set(tiers) == set(TIERS)
        assert tiers["strong"] is None
        assert tiers["standard"] and tiers["basic"]


def test_prose_planning_and_reader_roles_cannot_be_lowered_by_a_setting() -> None:
    override = ",".join(
        f"{prefix}=basic" for prefix in ("default", "writer.", "planner.", "reader.")
    )
    routing = ModelRouting.from_environ("codex", {"LITHARNESS_MODEL_TIERS": override})
    for profile in ("default", "writer.discovery.v14", "planner.outline.v8", "reader.continue.v0"):
        assert routing.tier_for(profile) == "strong", profile
    assert not any(
        profile.startswith(pinned)
        for profile, _tier in CANDIDATE_ROLE_TIERS
        for pinned in PINNED_STRONG
        if pinned.endswith(".")
    )


def test_a_request_that_names_its_model_is_never_rerouted() -> None:
    routing = ModelRouting.from_environ("claude", {"LITHARNESS_MODEL_TIERS": "candidate"})
    pinned = CompletionRequest(prompt="x", profile="mechanical", model="claude-haiku-4-5-20251001")
    assert routing.route(pinned) is pinned


def test_an_override_replaces_a_tier_model_on_the_day_one_is_unavailable() -> None:
    routing = ModelRouting.from_environ(
        "codex",
        {"LITHARNESS_MODEL_TIERS": "candidate", "LITHARNESS_CODEX_MODELS": "basic=gpt-6-sol"},
    )
    routed = routing.route(CompletionRequest(prompt="x", profile="title.availability.v0"))
    assert routed.model == "gpt-6-sol"


@pytest.mark.parametrize(
    "environ",
    [
        {"LITHARNESS_MODEL_TIERS": "architect.=cheap"},
        {"LITHARNESS_MODEL_TIERS": "architect."},
        {"LITHARNESS_CLAUDE_MODELS": "tiny=claude-haiku-4-5"},
    ],
)
def test_a_malformed_setting_is_refused_rather_than_guessed(environ: dict[str, str]) -> None:
    with pytest.raises(ValueError):
        ModelRouting.from_environ("claude", environ)


def test_the_registry_applies_routing_before_the_provider_sees_the_request() -> None:
    recorder = _Recorder()
    registry = ProviderRegistry(
        recorder,  # type: ignore[arg-type]
        routing=ModelRouting.from_environ("codex", {"LITHARNESS_MODEL_TIERS": "candidate"}),
    )
    registry.complete(CompletionRequest(prompt="x", profile="architect.grow.v5"))
    registry.complete(CompletionRequest(prompt="x", profile="default"))
    assert [request.model for request in recorder.seen] == ["gpt-6-sol", None]


def test_a_registry_without_routing_passes_requests_through() -> None:
    recorder = _Recorder()
    ProviderRegistry(recorder).complete(  # type: ignore[arg-type]
        CompletionRequest(prompt="x", profile="mechanical")
    )
    assert recorder.seen[0].model is None


def test_codex_runs_a_named_model_at_its_own_effort() -> None:
    provider = CodexCliProvider(
        model_efforts=codex_efforts({"LITHARNESS_CODEX_EFFORTS": "gpt-6-luna=high"})
    )
    assert provider.effort_for("gpt-6-luna") == "high"
    assert provider.effort_for("gpt-6-astra") == provider.reasoning_effort == "medium"


@pytest.mark.parametrize(
    ("value", "expected"),
    [("", "claude"), ("claude_code", "claude"), ("CODEX", "codex"), (" claude ", "claude")],
)
def test_one_setting_selects_the_whole_provider(value: str, expected: str) -> None:
    assert selected_provider({"LITHARNESS_PROVIDER": value} if value else {}) == expected


def test_an_unknown_provider_is_refused() -> None:
    with pytest.raises(ValueError):
        selected_provider({"LITHARNESS_PROVIDER": "gemini"})


def test_the_model_policy_page_carries_a_review_marker_and_names_the_mapped_models() -> None:
    """`docs/model-policy.md` owns when the map was last reviewed; its table must name the
    models the code maps, so the page and `routing.py` cannot drift apart silently."""
    text = (REPO / "docs" / "model-policy.md").read_text(encoding="utf-8")
    status = review_status(text)
    assert status is not None and status.interval_days == 14
    for tiers in PROVIDER_TIERS.values():
        for model in tiers.values():
            if model is not None:
                assert f"`{model}`" in text, model


def test_the_review_falls_due_on_its_interval() -> None:
    status = review_status("<!-- model-policy: last-reviewed 2026-09-22; interval-days 14 -->")
    assert status is not None
    assert status.due == date(2026, 10, 6)
    assert not status.overdue(date(2026, 10, 5))
    assert status.overdue(date(2026, 10, 6))
    assert review_status("no marker here") is None


def test_the_models_view_reports_roles_without_opening_a_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LITHARNESS_PROVIDER", "codex")
    monkeypatch.setenv("LITHARNESS_MODEL_TIERS", "candidate")
    assert cli.main(["--database", str(tmp_path / "absent.db"), "models", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["provider"] == "codex"
    assert report["tiers"]["standard"] == "gpt-6-sol"
    by_role = {row["role"]: row for row in report["roles"]}
    assert by_role["world grow"]["model"] == "gpt-6-sol"
    assert by_role["scene drafting"]["tier"] == "strong"
    assert report["review"]["last_reviewed"] == "2026-09-22"
    assert not (tmp_path / "absent.db").exists()
