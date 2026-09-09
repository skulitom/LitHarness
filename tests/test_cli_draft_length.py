"""Configured scene lengths must fit the CLI's finite runaway ceiling."""

from __future__ import annotations

from dataclasses import replace

import pytest

from litharness import cli
from litharness.adapters.sqlite_store import SqliteStore
from litharness.application.conductor import TickOutcome
from litharness.application.handlers import draft_sampler
from litharness.domain.draft import DraftPolicy, gate_draft
from litharness.domain.patch import Veto
from litharness.domain.policy import Outcome, policy_digest
from tests.conftest import PROJECT_ID
from tests.test_draft import START, blank_revision, registry_with, seeded


@pytest.mark.parametrize("target", [None, 0, 400, 900])
def test_default_and_shorter_cli_targets_keep_existing_shape_bounds(target) -> None:
    options = [] if target is None else ["--target-words", str(target)]
    policy = cli._draft_policy(cli.build_parser().parse_args([*options, "tick"]))
    assert policy == replace(DraftPolicy(), target_words=900 if target is None else target)


def test_long_cli_target_reaches_acceptance_with_its_effective_ceiling(
    tmp_path, monkeypatch,
) -> None:
    # A normal-sized 1,700-word answer exceeds the old 8,000-character ceiling.
    text = " ".join(["lantern"] * 1700)
    args = cli.build_parser().parse_args([
        "--project", PROJECT_ID, "--target-words", "1800", "tick",
    ])
    policy = cli._draft_policy(args)
    assert policy.target_words == 1800 and policy.max_chars == 16000
    assert DraftPolicy().max_chars < len(text) < policy.max_chars
    registry, provider = registry_with(text)
    monkeypatch.setattr(cli, "build_default_registry", lambda: registry)

    with SqliteStore.open(tmp_path / "long-draft.db") as store:
        original = seeded(store)
        result = cli._conductor(store, args).tick(START)
        assert result.outcome is TickOutcome.RAN_JOB
        assert provider.calls == 1
        decision = store.latest_decision_for("draft-1")
        assert decision is not None and decision.outcome is Outcome.ACCEPT
        assert decision.base_revision_id == original.revision_id
        assert decision.resulting_revision_id is not None
        accepted = store.load_revision(decision.resulting_revision_id)
        assert accepted.node("scene-1").content == text
        sampler = draft_sampler(store.load_job("draft-1"), "default")
        assert decision.policy_config_digest == policy_digest(policy, sampler)
        assert decision.policy_config_digest != policy_digest(
            replace(policy, max_chars=DraftPolicy().max_chars), sampler,
        )


def test_long_cli_target_preserves_stub_and_runaway_guards_without_a_word_floor() -> None:
    policy = cli._draft_policy(cli.build_parser().parse_args(["--target-words", "1800", "tick"]))
    revision = blank_revision()
    # An intentionally short but complete-shaped answer is still permitted.
    assert gate_draft(revision, "scene-1", "word " * 50, policy=policy).accepted
    assert gate_draft(revision, "scene-1", "Too short.", policy=policy).veto_kinds == (
        Veto.LENGTH_MOVEMENT,
    )
    runaway = gate_draft(revision, "scene-1", "word " * 5000, policy=policy)
    assert runaway.veto_kinds == (Veto.LENGTH_MOVEMENT,)
    assert str(policy.max_chars) in runaway.vetoes[0].detail


def test_explicit_domain_ceiling_is_not_relaxed_by_a_longer_target() -> None:
    policy = DraftPolicy(target_words=1800, max_chars=8000)
    outcome = gate_draft(blank_revision(), "scene-1", " ".join(["lantern"] * 1700), policy=policy)
    assert outcome.veto_kinds == (Veto.LENGTH_MOVEMENT,)
    assert "ceiling of 8000" in outcome.vetoes[0].detail
