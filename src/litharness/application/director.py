"""The Director producer: one bounded piece of direction per block of accepted scenes.

**The Director is never shown the prose, and that is the enforcement rather than an
optimisation.** A role that cannot see the text cannot render a verdict on it, so "a Director
may not evaluate prose" stops being an instruction a model might drift from and becomes a
property of what it was handed. What it gets instead is *structural* state — the premise, the
scene statements, what has been drafted, what the ledger still owes, and the summaries of scenes
already accepted. Summaries say what happened; prose says how it reads, and only the second is
the frame that died three times (`plan/director-role.md` §0).

**Bounded by the book's progress, not by plan churn.** One directive per block of
`DIRECTIVE_EVERY` accepted scenes, keyed into the job id so a replayed tick converges onto the
same unit rather than minting a second. The obvious alternative — one per plan epoch — is a spin
loop wearing a bound: a directive becomes a plan application, a plan application bumps the epoch,
and the epoch was the thing licensing the next directive. Tying the cadence to *accepted scenes*
cannot do that, because nothing the Director says drafts a scene.

**Below human direction, always.** Both human lanes mint at 1000+ and 500+; this mints at
`DIRECT_PRIORITY` beneath them, so a directive a person drops mid-run is materialised first and a
machine can never bury it.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from litharness.application.conductor import JobHandler
from litharness.application.ports import DirectorStore, TextGenerator
from litharness.domain.directives import (
    Directive,
    DirectiveKind,
    DirectiveStatus,
    directive_id_for,
)
from litharness.domain.directors import (
    DIRECTOR_KINDS,
    Director,
    IllegalBrief,
    legal_brief,
    machine_author,
)
from litharness.domain.events import Event, EventType, payload_digest
from litharness.domain.generation import CompletionRequest, CompletionResult
from litharness.domain.jobs import Job, input_digest_for
from litharness.domain.nodes import NodeKind
from litharness.domain.plans import premise_of, scene_plan_for
from litharness.domain.revision import Revision

DIRECT = "direct"

#: Beneath both human direction lanes (1000+ verbatim, 500+ interpretive) and above the drafting
#: work it shapes. A machine that could outrank a person's instruction would be the opposite of
#: what §4.3 calls the direction inbox.
DIRECT_PRIORITY = 400

#: How many accepted scenes pass between one piece of machine direction and the next. Six, which
#: is one beat sheet's worth, so a thirty-scene book hears from its Director about five times.
#: **A placed number, labelled as one**: nothing has measured how often direction is worth
#: giving, and the honest way to find out is an arm rather than a constant somebody liked.
DIRECTIVE_EVERY = 6

PROFILE = "director.v0"

#: What the Director is allowed to answer with. `kind` is constrained to the interpretive set at
#: the schema, so a director that tried to issue a veto fails to conform rather than being
#: filtered afterwards — a refusal the provider layer reports as a retryable shape failure.
DIRECTIVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": sorted(kind.value for kind in DIRECTOR_KINDS)},
        "body": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["kind", "body"],
    "additionalProperties": False,
}


class DirectorInputError(ValueError):
    """The queued unit does not describe direction this handler can produce."""


class DirectorOutputError(ValueError):
    """The Director answered with something it is not licensed to say."""


def direct_job_id(book_id: str, branch_id: str, block: int) -> str:
    """Stable identity for "this book's Director speaks for scene-block N".

    Keyed on the block rather than on the plan epoch, so the unit is a fact about how far the
    book has got rather than about how much its plan has churned — and a replayed tick converges
    onto the same job instead of minting a second piece of direction.
    """
    material = payload_digest(
        {"book_id": book_id, "branch_id": branch_id, "block": block, "lane": "director.v0"}
    )
    return f"direct-{sha256(material.encode()).hexdigest()[:24]}"


def scene_block(revision: Revision | None) -> int:
    """Which direction block this book is in: accepted scenes // `DIRECTIVE_EVERY`."""
    if revision is None:
        return 0
    drafted = sum(
        1
        for node in revision.in_reading_order()
        if node.kind is NodeKind.SCENE and node.content and not node.tombstoned
    )
    return drafted // DIRECTIVE_EVERY


def render_request(
    director: Director,
    *,
    premise: str | None,
    statements: Sequence[tuple[str, str]],
    summaries: Mapping[str, str],
    drafted: int,
    of_total: int,
    open_promises: Sequence[str],
    call_class: str = "generation",
) -> CompletionRequest:
    """The Director's turn: the book's shape, its own brief, and no prose.

    The brief goes in the system message because it is standing and the book's state goes in the
    prompt because it moves — the same split `render_prompt` makes for the same reason, and the
    instruction goes last because the last thing in a prompt is the thing a model acts on.
    """
    lines: list[str] = []
    if premise:
        lines.append(f"PREMISE:\n{premise}")
    if statements:
        rendered = "\n".join(f"- {logical_id}: {text}" for logical_id, text in statements)
        lines.append(f"SCENE STATEMENTS:\n{rendered}")
    if summaries:
        rendered = "\n".join(f"- {key}: {value}" for key, value in sorted(summaries.items()))
        lines.append(f"WHAT HAS HAPPENED SO FAR:\n{rendered}")
    if open_promises:
        lines.append("STILL OWED:\n" + "\n".join(f"- {item}" for item in open_promises))
    lines.append(f"PROGRESS: {drafted} of {of_total} scenes drafted.")
    kinds = ", ".join(sorted(kind.value for kind in DIRECTOR_KINDS))
    lines.append(
        "Give this book ONE piece of direction, in your own voice, as JSON with `kind` "
        f"(one of {kinds}) and `body`.\n\n"
        "Direction is about the STORY — what happens, what it costs, who it is about, what "
        "the book is for. It is not about how the prose should read: do not instruct about "
        "sentences, punctuation, style, or how much of a character's inner life to put on the "
        "page. Those are decided elsewhere, from evidence you do not have."
    )
    return CompletionRequest(
        prompt="\n\n".join(lines),
        system=(
            f"You are {director.name}, directing a novel. This is your standing brief and it "
            f"is the whole of your taste:\n{director.brief}\n\n"
            "You never see the prose and you never judge it. You say what the book should be."
        ),
        schema=DIRECTIVE_SCHEMA,
        max_output_tokens=400,
        profile=PROFILE,
        call_class=call_class,
    )


def directive_from(
    result: CompletionResult, director: Director, *, book_id: str, branch_id: str, at: str
) -> Directive:
    """The Director's answer as a directive, or a refusal naming what it was not licensed to say.

    Three checks, and each refuses rather than repairs. The kind must be one a Director may
    emit — `CONSTRAINT` and `VETO` are the human director's authority and `CONTROL` is operator
    state. The body must be legal direction under `legal_brief`, which is the rail keeping a
    Director from pre-empting an axis the Reader/Judge loop is actively measuring. And the answer
    must have conformed at all: a malformed reply is a failed call, never an empty directive.
    """
    if result.parsed is None:
        raise DirectorOutputError("the director's answer did not satisfy the schema")
    raw_kind = result.parsed.get("kind")
    body = result.parsed.get("body")
    if not isinstance(raw_kind, str) or not isinstance(body, str) or not body.strip():
        raise DirectorOutputError("a directive needs a kind and a non-empty body")
    try:
        kind = DirectiveKind(raw_kind)
    except ValueError as error:
        raise DirectorOutputError(f"{raw_kind!r} is not a directive kind") from error
    if kind not in DIRECTOR_KINDS:
        raise DirectorOutputError(
            f"a director may not emit {kind.value}: refusal and operator state are the human "
            "director's (plan/director-role.md §1)"
        )
    try:
        legal_brief(body)
    except IllegalBrief as error:
        raise DirectorOutputError(f"the director's direction is not legal: {error}") from error
    author = machine_author(director.director_id)
    return Directive(
        directive_id=directive_id_for(kind, body.strip(), at, author),
        kind=kind,
        body=body.strip(),
        status=DirectiveStatus.RECEIVED,
        book_id=book_id,
        branch_id=branch_id,
        received_at=at,
        author=author,
        metadata={"director": director.name, "reason": result.parsed.get("reason", "")},
    )


def director_job(book_id: str, branch_id: str, block: int, director_id: str) -> Job:
    """The unit that asks one Director for one piece of direction."""
    payload: dict[str, object] = {
        "book_id": book_id,
        "branch_id": branch_id,
        "block": block,
        "director_id": director_id,
    }
    job_id = direct_job_id(book_id, branch_id, block)
    return Job(
        job_id=job_id,
        job_kind=DIRECT,
        idempotency_key=job_id,
        payload=payload,
        input_digest=input_digest_for(payload),
        priority=DIRECT_PRIORITY,
    )


def _timestamp(now: float) -> str:
    return datetime.fromtimestamp(now, tz=UTC).isoformat().replace("+00:00", "Z")


def make_director_handler(
    registry: TextGenerator,
    store: DirectorStore,
    project_id: str,
    *,
    call_class: str = "generation",
) -> JobHandler:
    """Ask this book's Director for one directive and drop it in the inbox."""

    def handle(job: Job, now: float) -> Sequence[Event]:
        payload = job.payload
        try:
            book_id = str(payload["book_id"])
            branch_id = str(payload["branch_id"])
            director_id = str(payload["director_id"])
        except (KeyError, TypeError) as error:
            raise DirectorInputError(
                f"job {job.job_id} payload lacks direction inputs: {error}"
            ) from error
        director = store.director(director_id)
        if director is None:
            raise DirectorInputError(
                f"job {job.job_id} names director {director_id}, which is not registered. "
                "Admitting a personality is an operator act (`litharness directors --register`)"
            )
        head = store.head(book_id, branch_id)
        plan_items = tuple(store.plan_items(book_id, branch_id))
        scenes = (
            [
                node
                for node in head.in_reading_order()
                if node.kind is NodeKind.SCENE and not node.tombstoned
            ]
            if head is not None
            else []
        )
        statements = []
        for node in scenes:
            item = scene_plan_for(plan_items, node.logical_id)
            if item is not None:
                statements.append((node.logical_id, item.text))
        stored = store.scene_summaries(book_id, branch_id) if head is not None else {}
        summaries: dict[str, str] = {}
        for logical_id, by_hash in stored.items():
            if by_hash:
                summaries[logical_id] = next(iter(by_hash.values()))
        drafted = sum(1 for node in scenes if node.content)
        promises = [
            promise.description
            for promise in store.promises(book_id, branch_id, open_only=True)
        ]
        request = render_request(
            director,
            premise=premise_of(plan_items),
            statements=statements,
            summaries=summaries,
            drafted=drafted,
            of_total=len(scenes),
            open_promises=promises[:10],
            call_class=call_class,
        )
        result, _resolution = registry.complete(request)
        directive = directive_from(
            result, director, book_id=book_id, branch_id=branch_id, at=_timestamp(now)
        )
        store.submit_directive(directive, received_at=_timestamp(now))
        return [
            Event(
                # There is no DirectiveReceived member in the contract's event vocabulary and
                # inventing one would need a minor version for something only this handler
                # emits. `PLAN_CHANGED` is the honest neighbour: a directive is the first half
                # of a plan change, and the payload says which director and which block.
                event_type=EventType.PLAN_CHANGED,
                project_id=project_id,
                created_at=_timestamp(now),
                book_id=book_id,
                branch_id=branch_id,
                actor=directive.author or "",
                payload={
                    "directive_id": directive.directive_id,
                    "kind": directive.kind.value,
                    "author": directive.author,
                    "director": director.name,
                    "block": payload.get("block"),
                },
            )
        ]

    return handle


__all__ = [
    "DIRECT",
    "DIRECTIVE_EVERY",
    "DIRECTIVE_SCHEMA",
    "DIRECT_PRIORITY",
    "PROFILE",
    "DirectorInputError",
    "DirectorOutputError",
    "direct_job_id",
    "directive_from",
    "director_job",
    "make_director_handler",
    "render_request",
    "scene_block",
]
