"""Prompt provenance must not perturb scene sampling or replace the full integrity digest."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any

import pytest

from litharness.application.handlers import SCENE_DRAFT, draft_sampler
from litharness.domain.jobs import Job, input_digest_for

SCHEMA = "litharness.prompt-sources.v1"


def _job(payload: dict[str, Any], *, kind: str = SCENE_DRAFT) -> Job:
    return Job(
        job_id="sampling-fixture",
        job_kind=kind,
        payload=payload,
        input_digest=input_digest_for(payload),
        attempts=2,
    )


def _payload() -> dict[str, Any]:
    return {
        "revision_id": "revision-before-instrumentation",
        "logical_id": "scene-1",
        "system": "Draft the scene.",
        "prompt": "A visitor asks for the missing ledger.",
        "context": {"tokens": 30},
    }


def test_adding_or_updating_source_metadata_preserves_the_previous_scene_sample() -> None:
    before = _job(_payload())
    first = _job({**before.payload, "prompt_sources": {"schema": SCHEMA, "entries": []}})
    second = _job(
        {
            **before.payload,
            "prompt_sources": {
                "schema": SCHEMA,
                "entries": [{"source": "scene-1-plan"}],
                "sampling_seed": 999,
            },
        }
    )
    frozen = deepcopy((first, second))

    assert draft_sampler(before, "default") == draft_sampler(first, "default")
    assert draft_sampler(before, "default") == draft_sampler(second, "default")
    assert len({before.input_digest, first.input_digest, second.input_digest}) == 3
    assert first.input_digest == input_digest_for(first.payload)
    assert second.input_digest == input_digest_for(second.payload)
    assert (first, second) == frozen


@pytest.mark.parametrize("key", ["prompt", "system", "logical_id", "revision_id", "context"])
def test_request_or_other_frozen_payload_changes_still_change_the_sample(key: str) -> None:
    payload = {**_payload(), "prompt_sources": {"schema": SCHEMA, "entries": []}}
    before = _job(payload)
    after = _job({**payload, key: "a changed input"})

    assert draft_sampler(before, "default").seed != draft_sampler(after, "default").seed
    assert (
        draft_sampler(before, "default").seed
        != draft_sampler(replace(before, attempts=before.attempts + 1), "default").seed
    )


@pytest.mark.parametrize("digest", [None, ""])
def test_no_digest_keeps_the_existing_job_id_fallback(digest: str | None) -> None:
    before = replace(_job(_payload()), input_digest=digest)
    instrumented = replace(before, payload={**before.payload, "prompt_sources": {"schema": SCHEMA}})
    different_input = replace(instrumented, payload={"prompt": "Different but unbound input."})

    assert draft_sampler(before, "default") == draft_sampler(instrumented, "default")
    assert draft_sampler(before, "default") == draft_sampler(different_input, "default")
    assert (
        draft_sampler(before, "default").seed
        != draft_sampler(replace(before, job_id="another-job"), "default").seed
    )


@pytest.mark.parametrize("kind", ["plan_refinement", "revision", "other"])
def test_other_job_kinds_keep_their_full_digest_sampling(kind: str) -> None:
    payload = {**_payload(), "prompt_sources": {"schema": SCHEMA}}
    job = _job(payload, kind=kind)
    old_sampling_path = replace(job, payload={})

    assert draft_sampler(job, "default") == draft_sampler(old_sampling_path, "default")
    assert (
        draft_sampler(job, "default").seed
        != draft_sampler(_job(_payload(), kind=kind), "default").seed
    )


@pytest.mark.parametrize("sidecar", [None, [], {}, {"schema": "unknown"}, {"schema": 1}])
def test_unrecognized_sidecars_keep_the_full_digest_sampling(sidecar: Any) -> None:
    job = _job({**_payload(), "prompt_sources": sidecar})

    assert draft_sampler(job, "default") == draft_sampler(replace(job, payload={}), "default")


def test_an_unmatched_digest_is_not_replaced_with_untrusted_payload_material() -> None:
    original = _job(_payload())
    mismatched = replace(
        original,
        payload={
            "prompt": "Changed without updating integrity",
            "prompt_sources": {"schema": SCHEMA},
        },
    )

    assert mismatched.input_digest != input_digest_for(mismatched.payload)
    assert draft_sampler(mismatched, "default") == draft_sampler(original, "default")


def test_non_sidecar_seed_fields_do_not_override_derived_sampling() -> None:
    first = _job({**_payload(), "prompt_sources": {"schema": SCHEMA}})
    extra_field = _job({**first.payload, "sampling_seed": draft_sampler(first, "default").seed})

    assert draft_sampler(extra_field, "default").seed != draft_sampler(first, "default").seed


def test_greedy_profile_still_has_no_seed() -> None:
    job = _job({**_payload(), "prompt_sources": {"schema": SCHEMA}})

    sampler = draft_sampler(job, "mechanical")
    assert sampler.temperature == 0.0 and sampler.seed is None
    assert sampler == draft_sampler(replace(job, attempts=99), "mechanical")
