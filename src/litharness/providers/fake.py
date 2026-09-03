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
import re
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Any

from litharness.providers.base import (
    CompletionRequest,
    CompletionResult,
    ProviderError,
    ProviderFailureKind,
    Usage,
    parse_schema_payload,
)

ScriptedResponse = str | CompletionResult | Exception


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


#: The book's own printed line, wherever the drafting call puts it in the system message.
#: Matched by its opening token only: this provider does not know what a status line means and
#: must not learn — the columns, the labels and the subject are the book's, and every one of
#: them is carried through untouched.
_STATUS_LINE = re.compile(r"^\[STATUS\] .*$", re.MULTILINE)

#: An integer that is not the second half of an `n/m` pair. A paired column's maximum is a
#: ceiling the book declared rather than a value anybody moves, so moving it would write a
#: state no advancement produces.
_MOVABLE_NUMBER = re.compile(r"(?<![\d/])(\d+)")


def _carried(system: str | None) -> str | None:
    """The book's status line with every unpaired number moved by one, or `None`.

    **Why a deterministic provider prints a line at all.** `pad_to_chars`' note records the rule
    this follows: a model-free autonomous run that cannot clear a mechanical gate poisons every
    beat and leaves a green board over an empty manuscript, and the answer taken then was to
    make the fake *conforming* rather than to loosen `min_chars` — "a gate loosened to make a
    test pass is not a gate". §184's progression gate is the second mechanical gate to reach
    this provider: a scene whose plan named a quantity as moving is refused where the state it
    writes down holds that quantity still, and echo-and-filler output writes no state down at
    all.

    **Every number, and not the one the beat named.** Reading which column was asked for would
    mean this provider knowing the house's own beat sentence, which is a second home for text
    that lives in `domain/genre.py`. Moving all of them is the same mechanical trick padding is:
    it makes the fake satisfy a contract without making it look like it understood one.
    """
    if not system:
        return None
    found = _STATUS_LINE.findall(system)
    if not found:
        return None
    return _MOVABLE_NUMBER.sub(lambda match: str(int(match.group(1)) + 1), found[-1])


def _padded(text: str, target: int, digest: str) -> str:
    """Extend ``text`` to ``target`` characters with filler derived from ``digest``.

    Derived rather than random so the provider stays deterministic: the same request must
    produce the same bytes, or content-addressed revisions stop collapsing on replay and
    the endurance and idempotency properties quietly break.
    """
    if target <= 0 or len(text) >= target:
        return text
    words = [f"{digest[index : index + 4]}" for index in range(0, 40, 4)]
    filler: list[str] = []
    length = len(text)
    while length < target:
        word = words[len(filler) % len(words)]
        filler.append(word)
        length += len(word) + 1
    return f"{text} " + " ".join(filler)


@dataclass
class FakeProvider:
    name: str = "fake"
    bills: bool = False
    model: str = "fake-deterministic-v1"
    #: Canned answers by request digest, for tests that need specific text.
    canned: dict[str, str] = field(default_factory=dict)
    #: Set to raise on the next call, for exercising the failure path.
    fail_with: Exception | None = None
    #: FIFO responses for multi-attempt tests. None keeps digest-derived behaviour; an
    #: empty list means a configured script was exhausted and fails loudly.
    responses: list[ScriptedResponse] | None = None
    #: Pad free-text output to at least this many characters. 0 disables it.
    #:
    #: Exists because the default answer is ~140 characters and `DraftPolicy.min_chars` is
    #: 200, so a model-free autonomous run would fail the shape gate on every beat and
    #: poison the whole book — a green board over an empty manuscript. The alternative was
    #: lowering `min_chars`, and `domain/draft.py` forbids exactly that class of
    #: convenience relaxation: a gate loosened to make a test pass is not a gate.
    #:
    #: Opt-in, and the filler is a pure function of the request digest, so a replayed
    #: request still produces byte-identical output and content addressing still collapses.
    pad_to_chars: int = 0
    #: Echo the book's own status line with its numbers moved. See `_carried` for the rule this
    #: follows, which is `pad_to_chars`' own.
    #:
    #: **A second field rather than a widening of that one, and the reason is a book this
    #: cannot be safe on.** An imported book arrives holding a snapshot for every story
    #: position at once — both golden fixtures do — so a scene there is shown the numbers its
    #: own author stated for its position, and writing different ones mints a second canon
    #: snapshot at one key: the shape `integrity.detect_contradictions` groups on and refuses.
    #: Padding such a book is ordinary; moving its numbers is a contradiction. So the switch is
    #: separate, and `build_default_registry` is the one caller that sets it — the model-free run of
    #: the real loop, which drafts a book it created rather than one it imported.
    carry_status: bool = False
    calls: int = 0

    def health(self) -> bool:
        return True

    def set_responses(self, responses: list[ScriptedResponse]) -> None:
        self.responses = list(responses)

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        if self.fail_with is not None:
            raise self.fail_with

        if self.responses is not None:
            if not self.responses:
                raise ProviderError(
                    "no scripted fake responses remain",
                    kind=ProviderFailureKind.INVALID_REQUEST,
                )
            scripted = self.responses.pop(0)
            if isinstance(scripted, Exception):
                raise scripted
            if isinstance(scripted, CompletionResult):
                return scripted
            return self._result(request, scripted, digest=_digest(request))

        digest = _digest(request)
        if digest in self.canned:
            text = self.canned[digest]
        elif request.schema is not None:
            text = json.dumps(_synthesise(request.schema, digest), sort_keys=True)
        else:
            text = f"[fake:{digest[:12]}] {request.prompt.strip()[:120]}"
            text = _padded(text, self.pad_to_chars, digest)
            carried = _carried(request.system) if self.carry_status else None
            if carried is not None:
                text = f"{text}\n\n{carried}"

        return self._result(request, text, digest=digest)

    def _result(self, request: CompletionRequest, text: str, *, digest: str) -> CompletionResult:
        return CompletionResult(
            text=text,
            provider=self.name,
            # The model this call asked for, falling back to this adapter's own. The real
            # adapter reports what actually wrote the text and a fake has no second model to
            # report, but a role that names a model must be able to see its own name on the
            # decision row without a paid call, or the attribution is untested until it costs
            # money.
            model=request.model or self.model,
            usage=Usage(
                input_tokens=request.input_chars // 4,
                output_tokens=len(text) // 4,
            ),
            parsed=parse_schema_payload(text, request.schema),
            schema_requested=request.schema is not None,
            cost_usd=0.0,
            wall_ms=0,
            raw={"digest": digest, "provider": self.name},
        )
