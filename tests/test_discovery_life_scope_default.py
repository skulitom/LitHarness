"""Wire the registered sentence correction without changing the experiment's frozen tests."""

import hashlib

from litharness.application import discovery
from tests.test_discovery_life_scope_experiment import experiment


def test_production_discovery_uses_exactly_the_registered_scoped_system():
    request = discovery.render_request("EXACT_SOURCE", person="third")
    assert request.profile == "writer.discovery.v11"
    assert request.system.count(experiment.SCOPED) == 1
    assert experiment.ORIGINAL not in request.system
    full_system = request.system.replace(experiment.SCOPED, experiment.ORIGINAL)
    # Unseeded v10 system captured by every full control in evidence.json.
    assert hashlib.sha256(full_system.encode("utf-8")).hexdigest() == (
        "3042e2246e59e00298dab7b4177320d05cc2d2ecf56cbd80d313379c096ebc18"
    )
    assert discovery.DIRECTIONS["magical-discovery.v5"].replace(
        experiment.ORIGINAL, experiment.SCOPED
    ) == discovery.DIRECTION
