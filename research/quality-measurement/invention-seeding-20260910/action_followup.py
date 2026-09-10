"""Prepare and run the registered two-response first-use follow-up."""

from __future__ import annotations

import argparse
import dataclasses
from pathlib import Path

import run as baseline

HERE = baseline.HERE / "action-followup"
LOCAL = baseline.LOCAL / "action-followup"
FIRST_USE = (
    "First rewarding use of the shadow power: during the losing siege, the duelist manifests "
    "a stolen shadow behind the enemy commander and coordinates with its original owner to "
    "ambush and capture the commander. The captive is needed alive to identify the target of "
    "the old revenge oath. Let this combat success give the protagonist a useful lead and "
    "escape opportunity, while the owner's continuing control complicates the fight."
)


def prepare() -> None:
    baseline.lock()
    if (LOCAL / "manifest.json").exists():
        raise RuntimeError("Already prepared")
    from litharness.application import discovery

    if not Path(discovery.__file__).is_relative_to(baseline.BASELINE / "source"):
        raise RuntimeError("Use the baseline's frozen interpreter")
    original = baseline.read(baseline.LOCAL / "manifest.json")
    if any(baseline.sha(Path(p)) != h for p, h in original["files"].items()):
        raise RuntimeError("Original frozen files changed")
    packet = baseline.read(baseline.LOCAL / "packets/seed-00002.json")
    request = discovery.render_request(packet["brief"] + "\n" + FIRST_USE, person="third")
    files = dict(original["files"])
    for path in (Path(__file__), HERE / "RUNBOOK.md"):
        files[str(path.resolve())] = baseline.sha(path)
    order = ["action-1", "action-2"]
    for name in order:
        path = LOCAL / "requests" / f"{name}.json"
        baseline.write(path, dataclasses.asdict(request))
        files[str(path)] = baseline.sha(path)
    baseline.write(
        LOCAL / "manifest.json",
        {
            "order": order,
            "files": files,
            "binary": original["binary"],
            "token_stop": 22000,
        },
    )
    baseline.write(
        HERE / "registration.json",
        {
            "manifest_sha256": baseline.sha(LOCAL / "manifest.json"),
            "order": order,
            "parent_registration_sha256": baseline.sha(baseline.HERE / "registration.json"),
            "original_packet": 2,
            "comparison": "post-hoc, more prescriptive author brief",
            "request_sha256": {
                name: baseline.sha(LOCAL / "requests" / f"{name}.json") for name in order
            },
            "model": "gpt-6-astra",
            "effort": "medium",
            "native_sampler_seed": None,
        },
    )
    print("Prepared two follow-up requests; no model calls")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "run"))
    args = parser.parse_args()
    if args.mode == "prepare":
        prepare()
    else:
        baseline.HERE, baseline.LOCAL = HERE, LOCAL
        baseline.run()
