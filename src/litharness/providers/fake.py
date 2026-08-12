"""The deterministic provider. No model, no network, no cost.

This is the adapter Stage 0's whole test suite runs against, and it is the reason
"revisions, patches, events, and restore work end-to-end without a model" is a testable
claim rather than a hope. Output is a pure function of the request digest, so a replayed
job produces byte-identical text and the idempotency properties hold end to end.

It also satisfies a schema when one is asked for, by synthesising a minimal conforming
object. Without that, every schema-shaped code path would be untestable without a real
model — which is exactly the path most likely to be wrong.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

from litharness.providers.base import (
    CompletionRequest,
    CompletionResult,
    Usage,
    parse_schema_payload,
)


def _digest(request: CompletionRequest) -> str:
    material = json.dumps(
        {
            "prompt": request.prompt,
            "system": request.system,
            "schema": request.schema,
            "profile": request.profile,
            "max_output_tokens": request.max_output_tokens,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return sha256(material.encode("utf-8")).hexdigest()


def _synthesise(schema: dict[str, Any], seed: str) -> dict[str, Any]:
    """A minimal object satisfying ``schema``'s required keys and declared types."""
    payload: dict[str, Any] = {}
    properties = schema.get("properties", {})
    for key in schema.get("required", list(properties)):
        spec = properties.get(key, {})
        if "const" in spec:
            payload[key] = spec["const"]
            continue
        if spec.get("enum"):
            payload[key] = spec["enum"][0]
            continue
        match spec.get("type"):
            case "integer":
                payload[key] = 0
            case "number":
                payload[key] = 0.0
            case "boolean":
                payload[key] = True
            case "array":
                payload[key] = []
            case "object":
                payload[key] = {}
            case "null":
                payload[key] = None
            case _:
                payload[key] = f"{key}-{seed[:8]}"
    return payload


@dataclass
class FakeProvider:
    name: str = "fake"
    bills: bool = False
    model: str = "fake-deterministic-v1"
    #: Canned answers by request digest, for tests that need specific text.
    canned: dict[str, str] = field(default_factory=dict)
    #: Set to raise on the next call, for exercising the failure path.
    fail_with: Exception | None = None
    calls: int = 0

    def health(self) -> bool:
        return True

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        if self.fail_with is not None:
            raise self.fail_with

        digest = _digest(request)
        if digest in self.canned:
            text = self.canned[digest]
        elif request.schema is not None:
            text = json.dumps(_synthesise(request.schema, digest), sort_keys=True)
        else:
            text = f"[fake:{digest[:12]}] {request.prompt.strip()[:120]}"

        return CompletionResult(
            text=text,
            provider=self.name,
            model=self.model,
            usage=Usage(
                input_tokens=len(request.prompt) // 4,
                output_tokens=len(text) // 4,
            ),
            parsed=parse_schema_payload(text, request.schema),
            schema_requested=request.schema is not None,
            cost_usd=0.0,
            wall_ms=0,
            raw={"digest": digest, "provider": self.name},
        )
