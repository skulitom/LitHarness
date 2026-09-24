"""Wire the registered sentence correction without changing the experiment's frozen tests."""

import hashlib

from litharness.application import discovery
from tests.test_discovery_life_scope_experiment import experiment


def test_production_discovery_uses_exactly_the_registered_scoped_system():
    request = discovery.render_request("EXACT_SOURCE", person="third")
    assert request.profile == "writer.discovery.v16"
    assert request.system.count(experiment.SCOPED) == 1
    assert experiment.ORIGINAL not in request.system
    assert request.system.count(discovery.WORLD_DIRECTION) == 1
    # v12 adds a prospective experience brief, and v14 the restored world direction and
    # magical-discovery.v7's hook sentence (stage-0 §255); the previous world direction stays
    # exact.
    prior_system = (
        request.system.replace(discovery.WORLD_DIRECTION + "\n", "")
        .replace(discovery.EXPERIENCE_TASK, "")
        .replace("in the four fields", "in the three fields")
        .replace(discovery.DIRECTION, discovery.DIRECTIONS["magical-discovery.v6"])
    )
    full_system = prior_system.replace(experiment.SCOPED, experiment.ORIGINAL)
    # Unseeded v10 system captured by every full control in evidence.json.
    assert hashlib.sha256(full_system.encode("utf-8")).hexdigest() == (
        "3042e2246e59e00298dab7b4177320d05cc2d2ecf56cbd80d313379c096ebc18"
    )
    assert discovery.DIRECTIONS["magical-discovery.v5"].replace(
        experiment.ORIGINAL, experiment.SCOPED
    ) == discovery.DIRECTIONS["magical-discovery.v6"]
